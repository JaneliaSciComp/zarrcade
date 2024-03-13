import os
from functools import partial

import fsspec
from loguru import logger
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from ngffbrowse.images import yield_ome_zarrs, yield_images, get_fs

base_url = os.getenv("BASE_URL", 'http://127.0.0.1:8000/')

# The data location can be a local path or a cloud bucket URL -- anything supported by FSSpec
data_url = os.getenv("DATA_LOCATION")
if not data_url:
    raise Exception("You must define a DATA_URL environment variable " \
                    "pointing to a location where OME-Zarr images are found.")
logger.debug(f"Base URL is {data_url}")

fs, fsroot = get_fs(data_url)
logger.debug(f"Filesystem root is {fsroot}")
fsroot_dir = os.path.join(fsroot, '')
logger.debug(f"Filesystem dir is {fsroot_dir}")

images = []
id2image = {}
for zarr_path in yield_ome_zarrs(fs, fsroot):
    logger.info("Found images in "+zarr_path)
    logger.info("Removing prefix "+fsroot_dir)
    relative_path = zarr_path.removeprefix(fsroot_dir)
    logger.info("Relative path is "+relative_path)
    full_path = fsroot_dir + relative_path
    logger.info("Reading images in "+full_path)
    for image in yield_images(full_path, relative_path):
        images.append(image)
        id2image[image.id] = image
        logger.debug(image.__repr__())

def get_viewer_url(image, viewer):
    if isinstance(fs,fsspec.implementations.local.LocalFileSystem):
        url = os.path.join(base_url, "data", image.relative_path)
    else:
        url = image.full_path
    return viewer.get_viewer_url(url)

# Create the API
app = FastAPI(
    title="NGFF Browse Service",
    license_info={
        "name": "Janelia Open-Source Software License",
        "url": "https://www.janelia.org/open-science/software-licensing",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET","HEAD","OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "base_url": base_url,
            "images": images
        }
    )


@app.get("/views/{image_id:path}", response_class=HTMLResponse, include_in_schema=False)
async def views(request: Request, image_id: str):
    if image_id not in id2image:
        return Response(status_code=404)
    image = id2image[image_id]
    return templates.TemplateResponse(
        request=request, name="views.html", context={
            "data_url": data_url,
            "image": image,
            "get_viewer_url": partial(get_viewer_url, image)
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
