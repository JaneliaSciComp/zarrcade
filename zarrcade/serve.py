import os
import re
import sys
import signal
from io import StringIO
from functools import partial
from urllib.parse import urlencode

from loguru import logger
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from zarrcade.filestore import get_filestore
from zarrcade.database import Database, DBImage
from zarrcade.viewers import Viewer, Neuroglancer
from zarrcade.settings import get_settings, DataType, FilterType

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
    app.base_url = str(app.settings.base_url)
    logger.info(f"User-specified base URL is {app.base_url}")

    db_url = str(app.settings.db_url)
    logger.info(f"User-specified database URL is {db_url}")
    app.db = Database(db_url)

    for s in app.settings.filters:
        # Infer db name for the column if the user didn't provide it
        if s.db_name is None:
            try:
                s.db_name = app.db.reverse_column_map[s.column_name]
            except KeyError:
                logger.warning(f"Metadata missing column: {s.column_name}")
                continue

        # Get unique values from the database
        if s.data_type == DataType.string:
            s.values = app.db.get_unique_values(s.db_name)
        elif s.data_type == DataType.csv:
            s.values = app.db.get_unique_comma_delimited_values(s.db_name)

        logger.info(f"Configured {s.filter_type} filter for '{s.column_name}' ({len(s.values)} values)")

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


def get_proxy_url(collection: str, relative_path: str):
    """ Returns a web-accessible URL to the file store 
        which is proxied by this server.
    """
    return os.path.join(app.base_url, "data", collection,relative_path)


def get_data_url(dbimage: DBImage):
    """ Return a web-accessible URL to the given image.
    """
    # The data location can be a local path or a cloud bucket URL -- anything supported by FSSpec
    fs = get_filestore(dbimage.collection, app.settings.exclude_paths)
    image = dbimage.get_image()

    # Check if the collection is proxied
    proxy = next((p for p in app.settings.proxies if p.collection == dbimage.collection), None)
    if proxy:
        return os.path.join(str(proxy.url), image.relative_path)

    if fs.url:
        # This filestore is already web-accessible
        return os.path.join(fs.url, image.relative_path)

    # Proxy the data using the REST API
    return get_proxy_url(dbimage.collection, image.relative_path)


def get_relative_path_url(dbimage: DBImage, relative_path: str):
    """ Return a web-accessible URL to the given relative path.
    """
    if not relative_path:
        return None

    fs = get_filestore(dbimage.collection, app.settings.exclude_paths)
    if fs.url:
        # This filestore is already web-accessible
        return os.path.join(fs.url, relative_path)

    # Proxy the data using the REST API
    return get_proxy_url(dbimage.collection, relative_path)


def get_viewer_url(dbimage: DBImage, viewer: Viewer):
    """ Returns a web-accessible URL that opens the given image 
        in the specified viewer.
    """
    url = get_data_url(dbimage)
    if viewer==Neuroglancer:
        image = dbimage.get_image()
        if image.axes_order == 'tczyx':
            # Generate a multichannel config on-the-fly
            url = os.path.join(app.base_url, "neuroglancer", dbimage.collection, image.relative_path)
        else:
            # Prepend format for Neuroglancer to understand
            url = 'zarr://' + url

    return viewer.get_viewer_url(url)


def get_title(dbimage: DBImage):
    """ Returns the title to display underneath the given image.
    """
    settings = get_settings()
    col_name = app.db.reverse_column_map[settings.title_column_name]
    if col_name:
        try:
            metadata = dbimage.image_metadata
            if metadata:
                title = getattr(metadata, col_name)
                if title:
                    return title
        except KeyError:
            logger.warning(f"Missing column: {col_name}")

    return dbimage.get_image().relative_path


def get_query_string(query_params, **new_params):
    """ Takes the current query params, optionally overrides some parameters 
        and return a formatted query string.
    """
    return urlencode(dict(query_params) | new_params)


async def download_csv(request: Request, collection: str, search_string: str = ''):

    # Did the user select any filters?
    filter_params = {}
    for s in app.settings.filters:
        param_value = request.query_params.get(s.db_name)
        if param_value:
            filter_params[s.db_name] = param_value

    result = app.db.get_dbimages(collection, search_string, filter_params)
    column_map = app.db.column_map
    hide_columns = app.settings.details.hide_columns

    headers = ['Id','Collection','Name'] + [k for k in column_map.values() if k not in hide_columns]
    data = []

    for dbimage in result['images']:
        row = {
            'Id': dbimage.id,
            'Collection': dbimage.collection,
            'Name': dbimage.path
        }
        metadata = dbimage.image_metadata
        if metadata:
            for column in metadata.__table__.columns:
                if column.name not in hide_columns and column.name in app.db.column_map:
                    row[app.db.column_map[column.name]] = getattr(metadata, column.name)
        data.append(row)

    df = pd.DataFrame(data, columns=headers)

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)  # Go to the start of the buffer
    content = csv_buffer.getvalue()
    response = Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=data.csv"}
    )
    return response


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "settings": app.settings,
            "collection_map": app.db.collection_map
        }
    )


@app.get("/{collection}")
async def collection(request: Request, collection: str = '', search_string: str = '', page: int = 1, page_size: int=50):

    if request.query_params.get('download'):
        return await download_csv(request, collection, search_string)

    # Did the user select any filters?
    filter_params = {}
    for s in app.settings.filters:
        param_value = request.query_params.get(s.db_name)
        if param_value:
            filter_params[s.db_name] = param_value

    result = app.db.get_dbimages(collection, search_string, filter_params, page, page_size)

    return templates.TemplateResponse(
        request=request, name="collection.html", context={
            "settings": app.settings,
            "dbimages": result['images'],
            "get_viewer_url": get_viewer_url,
            "get_relative_path_url": get_relative_path_url,
            "get_data_url": get_data_url,
            "get_title": get_title,
            "get_query_string": partial(get_query_string, request.query_params),
            "search_string": search_string,
            "pagination": result['pagination'],
            "filter_params": filter_params,
            "FilterType": FilterType,
            "min": min,
            "max": max
        }
    )


@app.get("/details/{collection}/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def details(request: Request, collection: str, image_id: str):

    dbimage = app.db.get_dbimage(collection, image_id)
    if not dbimage:
        return Response(status_code=404)

    return templates.TemplateResponse(
        request=request, name="details.html", context={
            "settings": app.settings,
            "dbimage": dbimage,
            "column_map": app.db.column_map,
            "get_viewer_url": get_viewer_url,
            "get_relative_path_url": get_relative_path_url,
            "get_title": get_title,
            "get_data_url": get_data_url,
            "getattr": getattr
        }
    )


@app.head("/data/{collection}/{relative_path:path}")
async def data_proxy_head(relative_path: str, collection: str):
    try:
        data_url = app.db.collection_map[collection].data_url
        fs = get_filestore(data_url, app.settings.exclude_paths)
        size = fs.get_size(relative_path)
        headers = {}
        headers["Content-Type"] = "binary/octet-stream"
        headers["Content-Length"] = str(size)
        return Response(status_code=200, headers=headers)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/data/{collection}/{relative_path:path}")
async def data_proxy_get(relative_path: str, collection: str):
    try:
        data_url = app.db.collection_map[collection].data_url
        fs = get_filestore(data_url, app.settings.exclude_paths)
        with fs.open(relative_path) as f:
            data = f.read()
            headers = {}
            headers["Content-Type"] = "binary/octet-stream"
            return Response(status_code=200, headers=headers, content=data)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/neuroglancer/{collection}/{image_id:path}", response_class=JSONResponse, include_in_schema=False)
async def neuroglancer_state(collection: str, image_id: str):

    from neuroglancer.viewer_state import ViewerState, CoordinateSpace, ImageLayer
    dbimage = app.db.get_dbimage(collection, image_id)
    if not dbimage:
        return Response(status_code=404)

    image = dbimage.get_image()
    url = get_data_url(dbimage)

    if image.axes_order != 'tczyx':
        logger.error("Neuroglancer states can currently only be generated for TCZYX images")
        return Response(status_code=400)

    state = ViewerState()
    # TODO: dataclasses don't dsupport nested deserialization which makes this strange. Should switch to Pydantic.

    names = ['x','y','z','t']
    scales = []
    units = []
    position = []
    for name in names:
        axis = image.axes[name]
        scales.append(axis['scale'])
        units.append(axis['unit'])
        position.append(int(axis['extent'] / 2))

    state.dimensions = CoordinateSpace(names=names, scales=scales, units=units)
    state.position = position

    # TODO: how do we determine the best zoom from the metadata?
    state.crossSectionScale = 4.5
    state.projectionScale = 2048

    for i, channel in enumerate(image.channels):

        min_value = channel['pixel_intensity_min'] or 0
        max_value = channel['pixel_intensity_max'] or 4096

        color = channel['color']
        if re.match(r'^([\dA-F]){6}$', color):
            # bare hex color, add leading hash for rendering
            color = '#' + color

        layer = ImageLayer(
                source='zarr://'+url,
                layerDimensions=CoordinateSpace(names=["c'"], scales=[1], units=['']),
                localPosition=[i],
                tab='rendering',
                opacity=1,
                blend='additive',
                shader=(f"#uicontrol vec3 hue color(default=\"{color}\")\n"
                        f"#uicontrol invlerp normalized(range=[{min_value},{max_value}])\n"
                        f"void main(){{emitRGBA(vec4(hue*normalized(),1));}}")
            )

        start = channel['contrast_limit_start']
        end = channel['contrast_limit_end']

        # TODO: temporary hack to make Fly-eFISH data brighter
        end = min(end, 4000)

        if start and end:
            layer.shaderControls={
                    'normalized': {
                        'range': [start, end]
                    }
                }

        state.layers.append(name=channel['name'], layer=layer)

    state.layout = '4panel'
    return JSONResponse(state.to_json())
