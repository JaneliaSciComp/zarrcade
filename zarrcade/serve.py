import os
import re
import sys
import signal

from loguru import logger
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from zarrcade.filestore import Filestore
from zarrcade.database import Database
from zarrcade.model import Image
from zarrcade.viewers import Viewer, Neuroglancer
from zarrcade.settings import Settings

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

    # Override SIGINT to allow ctrl-c to work if startup takes too long
    orig_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, lambda s,f: sys.exit(128))

    # Load settings from config file and environment
    settings = Settings()
    app.base_url = str(settings.base_url)
    logger.info(f"Base URL is {app.base_url}")

    # The data location can be a local path or a cloud bucket URL -- anything supported by FSSpec
    app.data_url = str(settings.data_url)
    logger.info(f"Data URL is {app.data_url}")
    app.fs = Filestore(app.data_url)

    app.db_url = str(settings.db_url)
    logger.info(f"Database URL is {app.db_url}")
    app.db = Database(app.db_url)

    count = app.db.get_images_count()
    if count:
        logger.info(f"Found {count} images in the database")
    else:
        app.db.persist_images(app.fs.fsroot, app.fs.yield_images)

    # Restore default SIGINT handler
    signal.signal(signal.SIGINT, orig_handler)


@app.on_event("shutdown")
async def shutdown_event():
    """ Clean up database connections when we shut down.
    """
    logger.info("Shutting down database connections")
    app.db.engine.dispose()


def get_data_url(image: Image):
    # TODO: this should probably be the other way around: return paths we know
    # are web-accessible, and proxy everything else
    if app.fs.is_local():
        # Proxy the data using the REST API
        return os.path.join(app.base_url, "data", image.relative_path)
    else:
        # Assume the path is web-accessible
        return os.path.join(app.fs.url, image.relative_path)
        #return app.fs.get_absolute_path(image.relative_path)


def get_relative_path_url(relative_path: str):
    if not relative_path:
        return None
    if app.fs.is_local() or not app.fs.url:
        # Proxy the data using the REST API
        return os.path.join(app.base_url, "data", relative_path)
    else:
        # Assume the path is web-accessible
        return os.path.join(app.fs.url, relative_path)


def get_viewer_url(image: Image, viewer: Viewer):
    url = get_data_url(image)
    if viewer==Neuroglancer:
        if image.axes_order == 'tczyx':
            # Generate a multichannel config on-the-fly
            url = os.path.join(app.base_url, "neuroglancer", image.relative_path)
        else:
            # Prepend format for Neuroglancer to understand
            url = 'zarr://' + url

    return viewer.get_viewer_url(url)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request, search_string: str = '', page: int = 1, page_size: int=50):
    result = app.db.find_metaimages(search_string, page, page_size)
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "base_url": app.base_url,
            "metaimages": result['images'],
            "get_viewer_url": get_viewer_url,
            "get_relative_path_url": get_relative_path_url,
            "get_image_data_url": get_data_url,
            "search_string": search_string,
            "pagination": result['pagination'],
            "min": min,
            "max": max
        }
    )


@app.get("/details/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def details(request: Request, image_id: str):

    metaimage = app.db.get_metaimage(image_id)
    if not metaimage:
        return Response(status_code=404)

    return templates.TemplateResponse(
        request=request, name="details.html", context={
            "data_url": app.data_url,
            "metaimage": metaimage,
            "get_viewer_url": get_viewer_url,
            "get_relative_path_url": get_relative_path_url,
            "image_data_url": get_data_url(metaimage.image)
        }
    )


@app.head("/data/{relative_path:path}")
async def data_proxy_head(relative_path: str):
    try:
        size = app.fs.get_size(relative_path)
        headers = {}
        headers["Content-Type"] = "binary/octet-stream"
        headers["Content-Length"] = str(size)
        return Response(status_code=200, headers=headers)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/data/{relative_path:path}")
async def data_proxy_get(relative_path: str):
    try:
        with app.fs.open(relative_path) as f:
            data = f.read()
            headers = {}
            headers["Content-Type"] = "binary/octet-stream"
            return Response(status_code=200, headers=headers, content=data)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/neuroglancer/{image_id:path}", response_class=JSONResponse, include_in_schema=False)
async def neuroglancer_state(image_id: str):

    from neuroglancer.viewer_state import ViewerState, CoordinateSpace, ImageLayer

    metaimage = app.db.get_metaimage(image_id)
    if not metaimage:
        return Response(status_code=404)

    image = metaimage.image
    url = get_data_url(image)

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
                shader=f"#uicontrol vec3 hue color(default=\"{color}\")\n#uicontrol invlerp normalized(range=[{min_value},{max_value}])\nvoid main(){{emitRGBA(vec4(hue*normalized(),1));}}",
            )

        start = channel['contrast_limit_start']
        end = channel['contrast_limit_end']
        if start and end:
            layer.shaderControls={
                    'normalized': {
                        'range': [start, end]
                    }
                }

        state.layers.append(name=channel['name'], layer=layer)

    state.layout = '4panel'
    return JSONResponse(state.to_json())
