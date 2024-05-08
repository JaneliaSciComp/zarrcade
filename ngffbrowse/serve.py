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
from sqlalchemy import create_engine, text, Table, Column, String, Integer, MetaData, func, select

from neuroglancer.viewer_state import ViewerState, CoordinateSpace, ImageLayer

from dataclasses import dataclass, asdict
import json

from .images import Image, MetadataImage, yield_ome_zarrs, yield_images, get_fs
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
        db_name = row['db_name']
        original_name = row['original_name']
        print(f"Registering column '{db_name}' for {original_name}")
        attr_map[db_name] = original_name
except:
    logger.info("No metadata columns defined")

# Create image table if necessary
metadata = MetaData()
images_table = Table('images', metadata,
                    Column('id', Integer, primary_key=True),
                    Column('collection', String, nullable=False),
                    Column('relpath', String, nullable=False),
                    Column('dataset', String, nullable=False),
                    Column('image_path', String, nullable=False, index=True),
                    Column('image_info', String, nullable=False))
metadata.create_all(engine)

fs, fsroot = get_fs(data_url)
logger.debug(f"Filesystem root is {fsroot}")

fsroot_dir = os.path.join(fsroot, '')
logger.debug(f"Filesystem dir is {fsroot_dir}")

with engine.connect() as connection:
    # Check if the image info is already populated
    query = select(func.count()).select_from(images_table) \
            .where(images_table.c.image_info.isnot(None))
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
                logger.debug(f"Persisting {image}")
                logger.debug(f"Persisting repr {image.__repr__()}")
                stmt = select(images_table).where(images_table.c.image_path == image.id)
                existing_row = connection.execute(stmt).fetchone()
                image_info = json.dumps(asdict(image))
                dataset = image.id.removeprefix(relative_path)
                if existing_row:
                    update_stmt = images_table.update(). \
                        where((images_table.c.collection == fsroot) &
                              (images_table.c.image_path == image.id)). \
                        values(relpath=relative_path,
                               dataset=dataset,
                               image_info=image_info)
                    result = connection.execute(update_stmt)
                    logger.info(f"Updated {image.id}")
                else:
                    insert_stmt = images_table.insert() \
                            .values(collection=fsroot, \
                                    relpath=relative_path, \
                                    dataset=dataset, \
                                    image_path=image.id, \
                                    image_info=image_info)
                    connection.execute(insert_stmt)
                    logger.info(f"Inserted {image.id}")

        # Persist database to disk
        connection.commit()


def parse_image_info(image_info: str):
    json_obj = json.loads(image_info)
    return Image(**json_obj)


def get_metadata(row_dict):
    metadata = {}
    for k in attr_map:
        if k in row_dict:
            metadata[attr_map[k]] = row_dict[k]
    return metadata


def get_metaimage(image_id: str):
    with engine.connect() as connection:
        select_stmt = images_table.select().where(images_table.c.image_path == image_id)
        existing_record = connection.execute(select_stmt).fetchone()
        if existing_record:
            row_dict = existing_record._mapping
            relpath = row_dict['relpath']
            image_info_json = row_dict['image_info']
            logger.info(f"Found {row_dict['image_path']} in image collection")
            if image_info_json:
                image = parse_image_info(image_info_json)
                full_query = text(f"SELECT * FROM metadata WHERE relpath = :relpath")
                result_df = pd.read_sql_query(full_query, con=engine, params={'relpath': relpath})
                for _, row_dict in result_df.iterrows():
                    metadata = get_metadata(row_dict)
                    metaimage = MetadataImage(relpath, image, metadata)
                    return metaimage
                logger.info(f"No metadata found, returning plain image {image.id}")
                return MetadataImage(relpath, image, {})
            else:
                logger.info(f"Image has no image_info: {image_id}")
        else:
            logger.info(f"No image found with relpath: {image_id}")
        return None


def find_metaimages(search_string: str):
    with engine.connect() as connection:
        if not search_string: 
            full_query = text(f"SELECT * FROM metadata")
            result_df = pd.read_sql_query(full_query, con=engine)
        else:
            cols = attr_map.keys() or ['relpath']
            query_string = " OR ".join([f"{col} LIKE :search_string" for col in cols])
            full_query = text(f"SELECT * FROM metadata WHERE {query_string}")
            result_df = pd.read_sql_query(full_query, con=engine, params={'search_string': '%'+search_string+'%'})

        images = []
        for _, row_dict in result_df.iterrows():
            metadata = get_metadata(row_dict)
            #TODO: improve performance by fetching all images in single query
            stmt = select(images_table).where(images_table.c.relpath == row_dict['relpath'])
            results = connection.execute(stmt).fetchall()
            if results:
                for record in results:
                    image_info_json = record.image_info
                    if image_info_json:
                        image = parse_image_info(image_info_json)
                        metaimage = MetadataImage(record.image_path, image, metadata)
                        images.append(metaimage)

        return images


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
async def index(request: Request, search_string: str = '', page: int = 0):
    metaimages = find_metaimages(search_string)
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "base_url": base_url,
            "metaimages": metaimages,
            "get_viewer_url": get_viewer_url,
            "get_thumbnail_url": get_thumbnail_url,
            "get_image_data_url": get_data_url,
            "search_string": search_string,
            "page": page
        }
    )


@app.get("/views/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def views(request: Request, image_id: str):

    metaimage = get_metaimage(image_id)
    if not metaimage:
        return Response(status_code=404)

    return templates.TemplateResponse(
        request=request, name="views.html", context={
            "data_url": data_url,
            "metaimage": metaimage,
            "get_viewer_url": get_viewer_url,
            "get_thumbnail_url": get_thumbnail_url,
            "image_data_url": get_data_url(metaimage.image)
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

    metaimage = get_metaimage(image_id)
    if not metaimage:
        return Response(status_code=404)
    
    image = metaimage.image
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
