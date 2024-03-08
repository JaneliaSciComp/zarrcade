import os

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger
from ngffbrowse.images import yield_ome_zarrs, yield_images, get_fs

# Configure logging
# log_level = config.get('LOG_LEVEL', "DEBUG")
# logger.remove()
# logger.add(sys.stderr, enqueue=True, level=log_level)

base_url = os.getenv("BASE_URL")
fs, fsroot = get_fs(base_url)

images = []
for zarr_path in yield_ome_zarrs(fs, fsroot):
    logger.info("Found images in",zarr_path)
    relative_path = zarr_path.removeprefix(fsroot)
    full_path = base_url + relative_path
    logger.info("Reading images in",full_path)
    for image in yield_images(full_path, relative_path):
        images.append(image)
        logger.debug(image.__repr__())

# Create the API
app = FastAPI(
    title="NGFF Browse Service",
    license_info={
        "name": "Janelia Open-Source Software License",
        "url": "https://www.janelia.org/open-science/software-licensing",
    },
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)#, include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html", context={
            "base_url": base_url,
            "images": images
        }
    )


@app.head("/data/{path}")
async def data_proxy_head(path):
    try:
        info = fs.info(path)
        headers = {}
        headers["Content-Type"] = "binary/octet-stream"
        headers["Content-Length"] = info['size']
        return Response(status_code=204, headers=headers)
    except FileNotFoundError:
        return Response(status_code=404)


@app.get("/data/{path}")
async def data_proxy_get(path):    
    try:
        with fs.open(path) as f:
            data = f.read()
            headers = {}
            headers["Content-Type"] = "binary/octet-stream"
            return Response(status_code=200, headers=headers, content=data)
    except FileNotFoundError:
        return Response(status_code=404)
