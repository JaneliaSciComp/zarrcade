import os
import re

import fsspec
import s3fs
from loguru import logger
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

import pandas as pd
from sqlalchemy import create_engine, text, Table, MetaData, func, select

from neuroglancer.viewer_state import ViewerState, CoordinateSpace, ImageLayer

from dataclasses import dataclass, asdict
import json

from .images import Image, yield_ome_zarrs, yield_images, get_fs
from .viewers import Viewer, Neuroglancer

base_url = os.getenv("BASE_URL", 'http://127.0.0.1:8000/')
logger.info(f"Base URL is {base_url}")

# The data location can be a local path or a cloud bucket URL -- anything supported by FSSpec
data_url = os.getenv("DATA_URL")
if not data_url:
    raise Exception("You must define a DATA_URL environment variable " \
                    "pointing to a location where OME-Zarr images are found.")
logger.info(f"Data URL is {data_url}")

# Initialize database
engine = create_engine('sqlite:///database.db')

# Read the attribute naming map from the database, if they exist
attr_map = {}
try:
    query = "SELECT * FROM metadata_columns"
    result_df = pd.read_sql_query(query, con=engine)
    for index, row in result_df.iterrows():
        attr_map[row['db_name']] = row['original_name']
except:
    logger.info("No metadata columns defined")

# Create metadata table if necessary
try:
    df = pd.DataFrame({
        'relpath': [],
        'image_info': []
    })
    df.set_index('relpath', inplace=True)
    df.to_sql('metadata', con=engine, if_exists='fail', index=True, index_label='relpath')
except ValueError:
    logger.info("Metadata table already exists")

metadata_table = Table('metadata', MetaData(), autoload_with=engine)

fs, fsroot = get_fs(data_url)
logger.debug(f"Filesystem root is {fsroot}")

fsroot_dir = os.path.join(fsroot, '')
logger.debug(f"Filesystem dir is {fsroot_dir}")

with engine.connect() as connection:
    # Check if the image info is already populated
    query = select(func.count()).select_from(metadata_table) \
            .where(metadata_table.c.image_info.isnot(None))
    result = connection.execute(query)
    count = result.scalar()

    if count:
        logger.info(f"Found {count} images in the database")
    else:
        # Walk the storage root and populate the database
        for zarr_path in yield_ome_zarrs(fs, fsroot):
            logger.info("Found images in "+zarr_path)
            logger.info("Removing prefix "+fsroot_dir)
            relative_path = zarr_path.removeprefix(fsroot_dir)
            logger.info("Relative path is "+relative_path)
            absolute_path = fsroot_dir + relative_path
            if isinstance(fs,s3fs.core.S3FileSystem):
                absolute_path = 's3://' + absolute_path
            logger.info("Reading images in "+absolute_path)
            for image in yield_images(absolute_path, relative_path):
                logger.debug(image.__repr__())
                data = {
                    'image_info': json.dumps(asdict(image))
                }
                # Try to update first
                update_stmt = metadata_table.update().\
                    where(metadata_table.c.relpath == image.id).\
                    values(data)
                result = connection.execute(update_stmt)
                logger.info(f"Updating {image.id}")

                if result.rowcount == 0:  # Check if the update took place
                    # Perform insert
                    insert_stmt = metadata_table.insert().values(data)
                    connection.execute(insert_stmt)
                    logger.info(f"Inserting {image.id}")

        # Persist database to disk
        connection.commit()


def parse_image_info(image_info: str):
    json_obj = json.loads(image_info)
    return Image(**json_obj)


def get_image(image_id: str):
    with engine.connect() as connection:
        select_stmt = metadata_table.select().where(metadata_table.c.relpath == image_id)
        existing_record = connection.execute(select_stmt).fetchone()
        print(existing_record)
        image_info = existing_record['image_info']
        if image_info: 
            return parse_image_info(image_info)
        return None
            

def get_data_url(image: Image):
    # TODO: this should probably be the other way around: return paths we know
    # are web-accessible, and proxy everything else
    if isinstance(fs,fsspec.implementations.local.LocalFileSystem):
        # Proxy the data using the REST API
        return os.path.join(base_url, "data", image.relative_path)
    else:
        # Assume the path is web-accessible
        return image.absolute_path


def get_thumbnail_url(image: Image):
    if image.thumbnail_path:
        return os.path.join(get_data_url(image), image.thumbnail_path)
    return None


def get_viewer_url(image: Image, viewer: Viewer):
    url = get_data_url(image)
    if viewer==Neuroglancer:
        if image.axes_order == 'tczyx':
            # Generate a config on-the-fly
            url = os.path.join(base_url, "neuroglancer", image.relative_path)
        else:
            # Prepend format for Neuroglancer to understand
            url = 'zarr://' + url

    return viewer.get_viewer_url(url)


def find_images(search_string: str):
    if not search_string: 
        full_query = text(f"SELECT * FROM metadata")
        result_df = pd.read_sql_query(full_query, con=engine)
    else:
        query_string = " OR ".join([f"{col} LIKE :search_string" for col in attr_map.keys()])
        full_query = text(f"SELECT * FROM metadata WHERE {query_string}")
        result_df = pd.read_sql_query(full_query, con=engine, params={'search_string': '%'+search_string+'%'})

    images = []
    for _, row in result_df.iterrows():
        image_info = row['image_info']
        if image_info:
            image = parse_image_info(image_info)
            images.append(image)

    return images


# Create the API
app = FastAPI(
    title="NGFFBrowse Service",
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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, search_string: str = None, page: int = 0):
    images = find_images(search_string)
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "base_url": base_url,
            "images": images,
            "get_viewer_url": get_viewer_url,
            "get_thumbnail_url": get_thumbnail_url,
            "get_image_data_url": get_data_url,
            "search_string": search_string,
            "page": page
        }
    )


@app.get("/views/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def views(request: Request, image_id: str):

    image = get_image(image_id)
    if not image:
        return Response(status_code=404)

    query = text(f"SELECT * FROM metadata WHERE c_path = :path")
    result_df = pd.read_sql_query(query, con=engine, params={'path': image_id})
    metadata = result_df.iloc[0].to_dict()
    attrs = {}
    for k in metadata.keys():
        if k == 'c_path': continue
        attrs[attr_map[k]] = metadata[k]

    return templates.TemplateResponse(
        request=request, name="views.html", context={
            "data_url": data_url,
            "image": image,
            "attrs": attrs,
            "get_viewer_url": get_viewer_url,
            "get_thumbnail_url": get_thumbnail_url,
            "image_data_url": get_data_url(image)
        }
    )


@app.head("/data/{relative_path:path}")
async def data_proxy_head(relative_path: str):
    try:
        path = os.path.join(fsroot, relative_path)
        info = fs.info(path)
        headers = {}
        headers["Content-Type"] = "binary/octet-stream"
        headers["Content-Length"] = str(info['size'])
        return Response(status_code=200, headers=headers)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/data/{relative_path:path}")
async def data_proxy_get(relative_path: str):
    try:
        path = os.path.join(fsroot, relative_path)
        with fs.open(path) as f:
            data = f.read()
            headers = {}
            headers["Content-Type"] = "binary/octet-stream"
            return Response(status_code=200, headers=headers, content=data)
    except FileNotFoundError:
        return Response(status_code=404)



@app.get("/neuroglancer/{image_id:path}", response_class=JSONResponse, include_in_schema=False)
async def neuroglancer_state(image_id: str):

    image = get_image(image_id)
    if not image:
        return Response(status_code=404)
    
    url = get_data_url(image)

    if image.axes_order != 'tczyx':
        logger.error("Neuroglancer states can currently only be generated for TCZYX images")
        return Response(status_code=400)

    state = ViewerState()

    names = ['x','y','z','t']
    scales = []
    units = []
    position = []
    for name in names:
        axis = image.axes[name]
        scales.append(axis.scale)
        units.append(axis.unit)
        position.append(int(axis.extent / 2))

    state.dimensions = CoordinateSpace(names=names, scales=scales, units=units)
    state.position = position

    # TODO: how do we determine the best zoom from the metadata?
    state.crossSectionScale = 4.5
    state.projectionScale = 2048

    for i, channel in enumerate(image.channels):

        min = channel.pixel_intensity_min or 0
        max = channel.pixel_intensity_max or 4096

        color = channel.color
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
                shader=f"#uicontrol vec3 hue color(default=\"{color}\")\n#uicontrol invlerp normalized(range=[{min},{max}])\nvoid main(){{emitRGBA(vec4(hue*normalized(),1));}}",
            )

        start = channel.contrast_limit_start
        end = channel.contrast_limit_end
        if start and end:
            layer.shaderControls={
                    'normalized': {
                        'range': [start, end]
                    }
                }

        state.layers.append(name=channel.name, layer=layer)

    state.layout = '4panel'
    return JSONResponse(state.to_json())
