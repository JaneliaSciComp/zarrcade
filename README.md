
# NGFF Browse

Web service for easily viewing a directory of [NGFF](https://github.com/ome/ngff) (e.g. OME-Zarr) images. Implements the following useful features:

* Automatic discovery of images on [any storage backend supported by fsspec](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations) including file system, AWS S3, Azure Blob, Google Cloud Storage, Dropbox, etc.
* Web gallery with convenient viewing links to OME-Zarr-compliant viewers
* Neuroglancer state generation for multichannel images
* File proxy any storage backend that needs it
* Support for optional image thumbnails

The [nf-omezarr](https://github.com/JaneliaSciComp/nf-omezarr) tool can be used to easily generate OME-Zarrs with thumbnails which are compatible with this web service.

## Usage

To run the server locally with Docker, just point it at your OME-Zarr data:

```bash
docker run -it -v /path/to/data:/data ghcr.io/janeliascicomp/ngffbrowse
```

By default your server will run port 8000, so it will be accessible at <http://127.0.0.1:8000>. You can change the port by setting the `PORT` environment variable:

```bash
docker run -it -v /path/to/data:/data -e PORT=8080 ghcr.io/janeliascicomp/ngffbrowse
```

If your server is running remotely it will need to use HTTPS in order to be able to accessible to the viewers. You'll need to provide a TLS certificate and a base URL for generating links to your server.

```bash
docker run -it -v /path/to/data:/data \
    -e KEY_FILE=/path/to/keyfile -e CERT_FILE=/path/to/certfile \
    -e BASE_URL=https://yourdomainname.org \
    ghcr.io/janeliascicomp/ngffbrowse
```

## Development

Install the necessary packages using conda and pip:

```bash
conda env create -f environment.yml -y
conda activate ngffbrowse
pip install neuroglancer  --no-dependencies
```

Start the development server, pointing it to your OME-Zarr data:

```bash
DATA_URL=/path/to/data uvicorn ngffbrowse.serve:app --host 0.0.0.0 --reload
```

## Docker build

To rebuild the Docker container:

```bash
docker build --no-cache docker -t ghcr.io/janeliascicomp/ngffbrowse:latest
docker push ghcr.io/janeliascicomp/ngffbrowse:latest
```

## Attributions

<https://www.iconsdb.com/black-icons/copy-link-icon.html>
