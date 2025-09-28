import os
import re
import sys
import signal
from io import StringIO
from functools import partial
from urllib.parse import urlencode

from loguru import logger
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
from zarrcade.filestore import get_filestore
from zarrcade.database import Database, DBImage
from zarrcade.viewers import Viewer, get_viewers, get_viewer
from zarrcade.settings import get_settings
from zarrcade.collection import DataType, FilterType, AuxImageMode, load_collection_settings

# Create the API
app = FastAPI(
    title="Zarrcade OME-NGFF Gallery",
    license_info={
        "name": "Janelia Open-Source Software License",
        "url": "https://www.janelia.org/open-science/software-licensing",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def custom_sort_filter(items):
    """Custom filter to sort items with None values first, then alphabetically."""
    if not isinstance(items, dict):
        return items

    # Convert to list of (key, value) tuples for sorting
    item_list = list(items.items())

    def sort_key(item):
        key = item[0]
        # None values get priority 0, others get priority 1
        # Then sort alphabetically within each group
        if key is None or key == "None":
            return (0, "")
        else:
            return (1, str(key).lower())

    return sorted(item_list, key=sort_key)

templates.env.filters["custom_sort"] = custom_sort_filter


@app.on_event("startup")
async def startup_event():
    """ Runs once when the service is first starting.
        Reads the configuration and checks the database for images.
        If the database is not already populated, this walks the file store to 
        discover images on-the-fly and persist them in the database.
    """

    # Override SIGINT to allow ctrl-c to work if startup takes too long
    orig_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(128))

    # Load settings from config file and environment
    app.settings = get_settings()

    logger.info(f"Settings:")
    logger.info(f"  base_url: {app.settings.base_url}")
    logger.info(f"  database.url: {app.settings.database.url}")
    logger.info(f"  title: {app.settings.title}")
    logger.info(f"  collection: {app.settings.collection}")
    app.base_url = str(app.settings.base_url)

    db_url = str(app.settings.database.url)
    app.db = Database(db_url)

    # Load collection settings
    app.collections = {}
    for collection in app.db.get_collections():
        collection_settings = load_collection_settings(collection.settings_path)
        app.collections[collection.name] = collection_settings

        for s in collection_settings.filters:
            # Infer db name for the column if the user didn't provide it
            if s.db_name is None:
                try:
                    reverse_column_map = app.db.get_reverse_column_map(collection.name)
                    s.db_name = reverse_column_map[s.column_name]
                except KeyError:
                    logger.warning(f"Metadata missing column: {s.column_name}")
                    continue

            # Get unique values from the database
            if s.data_type == DataType.string:
                s._values = app.db.get_unique_values(collection.name, s.db_name)
            elif s.data_type == DataType.csv:
                s._values = app.db.get_unique_comma_delimited_values(collection.name, s.db_name)

            logger.info(f"Configured {s.filter_type} filter for '{s.column_name}' ({len(s._values)} values)")

    count = app.db.get_images_count()
    logger.info(f"Found {count} images in the database")

    # Restore default SIGINT handler
    signal.signal(signal.SIGINT, orig_handler)


@app.on_event("shutdown")
async def shutdown_event():
    """ Clean up database connections when the service is shut down.
    """
    logger.info("Shutting down database connections")
    app.db.engine.dispose()


def get_collection_filestore(collection: str):
    """ Return the filestore for the given collection.
    """
    if app.collections[collection].discovery:
        data_url = str(app.collections[collection].discovery.data_url)
        return get_filestore(data_url)
    else:
        return get_filestore()


def get_proxy_url(collection: str, relative_path: str):
    """ Returns a web-accessible URL to the file store 
        which is proxied by this server.
    """
    return os.path.join(app.base_url, "data", collection, relative_path)


def get_data_url(dbimage: DBImage):
    """ Return a web-accessible URL to the given image.
    """
    # The data location can be a local path or a cloud bucket URL -- anything supported by FSSpec
    collection_name = dbimage.collection.name
    fs = get_collection_filestore(collection_name)

    # Check if the collection is proxied
    if app.collections[collection_name].discovery:
        proxy_url = app.collections[collection_name].discovery.proxy_url
        if proxy_url:
            return os.path.join(str(proxy_url), dbimage.image_path)

    web_url = fs.get_url(dbimage.image_path)
    if web_url:
        # This filestore is already web-accessible
        return web_url

    # Proxy the data using the REST API
    return get_proxy_url(collection_name, dbimage.image_path)


def get_relative_path_url(dbimage: DBImage, relative_path: str):
    """ Return a web-accessible URL to the given relative path.
    """
    if not relative_path:
        return None

    collection_name = dbimage.collection.name
    fs = get_collection_filestore(collection_name)
    url = fs.get_url(relative_path)
    if url:
        # This filestore is already web-accessible
        return url

    # Proxy the data using the REST API
    return get_proxy_url(collection_name, relative_path)


def get_aux_path_url(dbimage: DBImage, relative_path: str, request: Request):
    """ Return a web-accessible URL to the given relative path.
    """
    collection_name = dbimage.collection.name
    collection_settings = app.collections[collection_name]
    if collection_settings.aux_image_mode == AuxImageMode.absolute:
        return relative_path
    elif collection_settings.aux_image_mode == AuxImageMode.relative:
        return get_relative_path_url(dbimage, relative_path)
    elif collection_settings.aux_image_mode == AuxImageMode.static:
        return request.url_for('static', path=relative_path)
    else:
        raise ValueError(f"Unknown aux image mode: {collection_settings.aux_image_mode}")


def get_viewers(dbimage: DBImage):
    """ Return a list of viewers that are configured for the current collection.
    """
    collection_name = dbimage.collection.name
    collection_settings = app.collections[collection_name]
    viewers = collection_settings.viewers
    if not viewers:
        return get_viewers()
    return [get_viewer(viewer) for viewer in viewers]
    

def get_viewer_url(dbimage: DBImage, viewer: Viewer):
    """ Returns a web-accessible URL that opens the given image 
        in the specified viewer.
    """
    collection_name = dbimage.collection.name
    url = get_data_url(dbimage)
    if viewer==Viewer.NEUROGLANCER:
        # Generate a multichannel config on-the-fly
        url = os.path.join(app.base_url, "neuroglancer", collection_name, dbimage.image_path)

    return viewer.get_viewer_url(url)


def get_bff_url(collection_name: str):
    """ Returns a web-accessible URL to the given collection.
    """
    bff_base_url = "https://bff.allencell.org/app"
    column_widths = "File Name:0.5"
    # Get the first 3 column names from the collection metadata
    collection_settings = app.collections.get(collection_name)
    column_map = app.db.get_column_map(collection_name)
    hide_columns = collection_settings.hide_columns
    column_names = [k for k in column_map.values() if k not in hide_columns]
    
    if collection_settings and collection_settings.filters:
        # Extract column names from the filters
        column_widths += "," + ",".join(column_names[:3])
    source = {
        "name":f"{collection_name}-data",
        "type":"csv",
        "uri":os.path.join(app.base_url, collection_name, "data.csv")
    }
    source_metadata = {
        "name":f"{collection_name}-cols",
        "type":"csv",
        "uri":os.path.join(app.base_url, collection_name, "columns.csv")
    }
    import json
    encoded_params = {
        "c": column_widths,
        "v": "3",
        "source": json.dumps(source),
        "sourceMetadata": json.dumps(source_metadata)
    }
    
    # Now encode the entire query string
    query_string = urlencode(encoded_params, safe='=+/')
    return bff_base_url + "?" + query_string


def get_title(dbimage: DBImage):
    """ Returns the title to display underneath the given image.
    """
    collection_name = dbimage.collection.name
    collection_settings = app.collections[collection_name]
    reverse_column_map = app.db.get_reverse_column_map(collection_name)
    if collection_settings.title_column_name in reverse_column_map:
        col_name = reverse_column_map[collection_settings.title_column_name]
        if col_name:
            try:
                metadata = dbimage.image_metadata
                if metadata:
                    title = getattr(metadata, col_name)
                    if title:
                        return title
            except KeyError:
                logger.warning(f"Missing column: {col_name}")

    return dbimage.image_path


def get_query_string(query_params, **new_params):
    """ Takes the current query params, optionally overrides some parameters 
        and return a formatted query string.
    """
    return urlencode(dict(query_params) | new_params)


@app.get("/")
async def index(request: Request):
    # If collection is configured, redirect directly to that collection
    if app.settings.collection:
        if app.settings.collection in app.db.collection_map:
            return RedirectResponse(url=f"/{app.settings.collection}", status_code=302)
        else:
            logger.warning(f"Configured collection '{app.settings.collection}' not found in database")

    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "settings": app.settings,
            "collections": app.collections,
            "collection_map": app.db.collection_map
        }
    )


@app.get("/{collection_name}")
async def collection(request: Request, collection_name: str = '', search_string: str = '', page: int = 1, page_size: int=50):

    if collection_name not in app.db.collection_map:
        return Response(status_code=404)

    if request.query_params.get('download'):
        return await download_csv(request, collection_name, search_string)

    collection_settings = app.collections[collection_name]
    
    # Did the user select any filters?
    filter_params = {}
    for s in collection_settings.filters:
        param_value = request.query_params.get(s.db_name)
        if param_value:
            filter_params[s.db_name] = param_value

    result = app.db.get_dbimages(collection_name, search_string, filter_params, page, page_size)

    return templates.TemplateResponse(
        request=request, name="collection.html", context={
            "settings": app.settings,
            "collection_name": collection_name,
            "collection_settings": collection_settings,
            "dbimages": result['images'],
            "get_viewer_url": get_viewer_url,
            "get_viewers": get_viewers,
            "get_relative_path_url": get_relative_path_url,
            "get_aux_path_url": get_aux_path_url,
            "get_data_url": get_data_url,
            "get_title": get_title,
            "get_bff_url": get_bff_url,
            "get_query_string": partial(get_query_string, request.query_params),
            "search_string": search_string,
            "pagination": result['pagination'],
            "filter_params": filter_params,
            "FilterType": FilterType,
            "min": min,
            "max": max
        }
    )


def get_csv_response(df: pd.DataFrame, filename: str):
    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)  # Go to the start of the buffer
    content = csv_buffer.getvalue()
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.head("/{collection_name}/data.csv")
async def download_data_csv_head(collection_name: str):
    if collection_name not in app.db.collection_map:
        return Response(status_code=404)
    return Response(status_code=200)


@app.head("/{collection_name}/columns.csv")
async def download_columns_csv_head(collection_name: str):
    if collection_name not in app.db.collection_map:
        return Response(status_code=404)
    return Response(status_code=200)


@app.get("/{collection_name}/data.csv")
async def download_data_csv(request: Request, collection_name: str, search_string: str = ''):

    if collection_name not in app.db.collection_map:
        return Response(status_code=404)

    collection_settings = app.collections[collection_name]

    # Did the user select any filters?
    filter_params = {}
    for s in collection_settings.filters:
        param_value = request.query_params.get(s.db_name)
        if param_value:
            filter_params[s.db_name] = param_value

    result = app.db.get_dbimages(collection_name, search_string, filter_params)
    column_map = app.db.get_column_map(collection_name)
    hide_columns = collection_settings.hide_columns

    # Header names are chosen for compatibility with BioFile Finder
    column_names = [k for k in column_map.values() if k not in hide_columns]
    headers = ['File Path','File Name','Collection','Thumbnail','Neuroglancer'] + column_names
    data = []

    def strip_html(html_text):
        if html_text is None:
            return None
        return re.sub(r'<[^>]*>', '', html_text)

    for dbimage in result['images']:

        # Get thumbnail URL only if thumbnail path exists
        thumbnail_path = None
        if dbimage.image_metadata:
            thumbnail_path = get_aux_path_url(dbimage, dbimage.image_metadata.thumbnail_path, request)

        row = {
            'File Path': get_data_url(dbimage),
            'File Name': strip_html(get_title(dbimage)),
            'Collection': dbimage.collection.name,
            'Thumbnail': thumbnail_path,
            'Neuroglancer': get_viewer_url(dbimage, Viewer.NEUROGLANCER)
        }
        metadata = dbimage.image_metadata
        if metadata:
            for column in metadata.__table__.columns:
                if column.name not in hide_columns and column.name in column_map:
                    row[column_map[column.name]] = strip_html(getattr(metadata, column.name))
        data.append(row)

    df = pd.DataFrame(data, columns=headers)
    return get_csv_response(df, f"{collection_name}_images.csv")



@app.get("/{collection_name}/columns.csv")
async def download_columns_csv(request: Request, collection_name: str):

    if collection_name not in app.db.collection_map:
        return Response(status_code=404)

    collection_settings = app.collections[collection_name]
    column_map = app.db.get_column_map(collection_name)
    hide_columns = collection_settings.hide_columns
    data = []
    data.append(['File Path','Full URL to the image file',''])
    data.append(['File Name','Name of the image file',''])
    data.append(['Collection','Name of the collection',''])
    data.append(['Thumbnail','URL to the thumbnail image',''])
    data.append(['Neuroglancer','URL to the Neuroglancer view','Open file link'])
    for k in column_map.values():
        if k not in hide_columns:
            data.append([k, f"{k} value", ''])


    df = pd.DataFrame(data, columns=["Column Name", "Description", "Type"])
    return get_csv_response(df, f"{collection_name}_columns.csv")


@app.get("/details/{collection_name}/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def details(request: Request, collection_name: str, image_id: str):

    dbimage = app.db.get_dbimage(collection_name, image_id)
    if not dbimage:
        return Response(status_code=404)

    return templates.TemplateResponse(
        request=request, name="details.html", context={
            "settings": app.settings,
            "collection_settings": app.collections[collection_name],
            "dbimage": dbimage,
            "column_map": app.db.get_column_map(collection_name),
            "get_viewer_url": get_viewer_url,
            "get_viewers": get_viewers,
            "get_relative_path_url": get_relative_path_url,
            "get_aux_path_url": get_aux_path_url,
            "get_title": get_title,
            "get_data_url": get_data_url,
            "getattr": getattr
        }
    )


@app.head("/data/{collection_name}/{file_path:path}")
async def data_proxy_head(collection_name: str, file_path: str):
    try:
        fs = get_collection_filestore(collection_name)
        size = fs.get_size(file_path)
        headers = {}
        headers["Content-Type"] = "binary/octet-stream"
        headers["Content-Length"] = str(size)
        return Response(status_code=200, headers=headers)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/data/{collection_name}/{file_path:path}")
async def data_proxy_get(collection_name: str, file_path: str):
    try:
        fs = get_collection_filestore(collection_name)
        with fs.open(file_path) as f:
            data = f.read()
            headers = {}
            headers["Content-Type"] = "binary/octet-stream"
            return Response(status_code=200, headers=headers, content=data)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/neuroglancer/{collection_name}/{image_id:path}", response_class=JSONResponse, include_in_schema=False)
async def neuroglancer_state(collection_name: str, image_id: str):

    dbimage = app.db.get_dbimage(collection_name, image_id)
    if not dbimage:
        return Response(status_code=404)

    image = dbimage.get_image()
    url = get_data_url(dbimage)

    # if image.axes_order != 'tczyx':
    #     logger.error("Neuroglancer states can currently only be generated for TCZYX images")
    #     return Response(status_code=400)

    layer = '4panel-alt'
    if 'z' in image.axes_order:
        z_index = image.axes_order.index('z')
        if image.dimensions_voxels.split(' ✕ ')[z_index]=='1':
            layer = 'xy'

    state = {
        "layout": layer,
        "layers": [
            {
                "name": "", # must be provided
                "type": "auto",
                "source": "zarr://"+url
            }
        ],
    }

    return JSONResponse(state)
