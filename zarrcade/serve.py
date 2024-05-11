import os
import re
import fsspec
import s3fs
import pandas as pd

from loguru import logger
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from neuroglancer.viewer_state import ViewerState, CoordinateSpace, ImageLayer

from .database import Database
from .model import Image
from .images import yield_ome_zarrs, yield_images, get_fs
from .viewers import Viewer, Neuroglancer

base_url = os.getenv("BASE_URL", 'http://127.0.0.1:8000/')
logger.info(f"Base URL is {base_url}")

# The data location can be a local path or a cloud bucket URL -- anything supported by FSSpec
data_url = os.getenv("DATA_URL")
if not data_url:
    raise Exception("You must define a DATA_URL environment variable " \
                    "pointing to a location where OME-Zarr images are found.")
logger.info(f"Data URL is {data_url}")
fs, fsroot = get_fs(data_url)
logger.debug(f"Filesystem root is {fsroot}")

# Ensure dir ends in a path separator
fsroot_dir = os.path.join(fsroot, '')
logger.trace(f"Filesystem dir is {fsroot_dir}")

db_url = os.getenv("DB_URL", 'sqlite:///:memory:')
logger.info(f"Database URL is {db_url}")
db = Database(db_url)

# Temporarily cache relpath -> metadata id lookup table
metadata_ids = db.get_relpath_to_metadata_id_map(fsroot)

count = db.get_images_count()
if count:
    logger.info(f"Found {count} images in the database")
else:
    # Walk the storage root and populate the database
    count = 0
    for zarr_path in yield_ome_zarrs(fs, fsroot):
        logger.info("Found images in "+zarr_path)
        logger.trace("Removing prefix "+fsroot_dir)
        relative_path = zarr_path.removeprefix(fsroot_dir)
        logger.info("Relative path is "+relative_path)
        absolute_path = fsroot_dir + relative_path
        if isinstance(fs,s3fs.core.S3FileSystem):
            absolute_path = 's3://' + absolute_path

        logger.info("Reading images in "+absolute_path)
        for image in yield_images(absolute_path, relative_path):

            if relative_path in metadata_ids:
                metadata_id = metadata_ids[relative_path]
            else:
                metadata_id = None

            logger.debug(f"Persisting {image}")
            db.persist_image(fsroot, 
                        relpath=relative_path, 
                        dataset=image.id.removeprefix(relative_path),
                        image=image,
                        metadata_id=metadata_id)
            count += 1

    logger.info(f"Persisted {count} images to the database")


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
            # Generate a multichannel config on-the-fly
            url = os.path.join(base_url, "neuroglancer", image.relative_path)
        else:
            # Prepend format for Neuroglancer to understand
            url = 'zarr://' + url

    return viewer.get_viewer_url(url)


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


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, search_string: str = '', page: int = 1, page_size: int=10):
    result = db.find_metaimages(search_string, page, page_size)
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "base_url": base_url,
            "metaimages": result['images'],
            "get_viewer_url": get_viewer_url,
            "get_thumbnail_url": get_thumbnail_url,
            "get_image_data_url": get_data_url,
            "search_string": search_string,
            "pagination": result['pagination']
        }
    )


@app.get("/views/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def views(request: Request, image_id: str):

    metaimage = db.get_metaimage(image_id)
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

    metaimage = db.get_metaimage(image_id)
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
