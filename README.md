# ![zarrcade](https://github.com/JaneliaSciComp/zarrcade/assets/607324/c0935b03-7b93-4b48-b8bf-4ec7b5116cb9)

Web application for easily browsing collections of [NGFF](https://github.com/ome/ngff) (e.g. OME-Zarr) images. Implements the following useful features:

* Automatic discovery of images on [any storage backend supported by fsspec](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations) including file system, AWS S3, Azure Blob, Google Cloud Storage, Dropbox, etc.
* Web gallery with convenient viewing links to compliant viewers
* Neuroglancer state generation for multichannel images
* File proxy for non-public storage backends
* Support for optional image thumbnails

The [nf-omezarr](https://github.com/JaneliaSciComp/nf-omezarr) tool can be used to easily generate OME-Zarrs with thumbnails which are compatible with this web service.

## Usage

To run the server locally with Docker, just point it at your OME-Zarr data:

```bash
docker run -it -v /path/to/data:/data -p 8000:8000 ghcr.io/janeliascicomp/zarrcade
```

If your server is running remotely it will need to use HTTPS in order to be able to accessible to the viewers. You'll need to provide a TLS certificate and a base URL for generating links to your server.

```bash
docker run -it -v /path/to/data:/data \
    -e KEY_FILE=/path/to/keyfile \
    -e CERT_FILE=/path/to/certfile \
    -e BASE_URL=https://yourdomainname.org \
    ghcr.io/janeliascicomp/zarrcade
```
## Importing metadata

You can import metadata into zarrcade by pre-populating the database from a CSV file:

```bash
conda env create -f environment.yml -y
conda activate zarrcade
bin/import_metadata.py -i input.csv -r /root/data/dir --overwrite
```

The CSV file's first column must be a relative path pointing to OME-Zarr images within the root data directory. The remaining columns can be any metadata to be searched and displayed within the gallery:

```csv
Path,Line,Marker
relative/path/to/ome1.zarr,JKF6363,Blu
relative/path/to/ome2.zarr,JDH3562,Blu
```

## Development

Install the necessary packages using conda and pip:

```bash
conda env create -f environment.yml -y
conda activate zarrcade
pip install neuroglancer  --no-dependencies
```

Start the development server, pointing it to your OME-Zarr data:

```bash
DATA_URL=/path/to/data uvicorn zarrcade.serve:app --host 0.0.0.0 --reload
```

If you are running the service remote, you'll need to use HTTPS. Just point Uvicorn to your certificate and set your BASE_URL:

```bash
BASE_URL=https://myserver.mydomain.org:8000 DATA_URL=/path/to/data uvicorn zarrcade.serve:app --host 0.0.0.0 \
    --ssl-keyfile certs/cert.key --ssl-certfile certs/cert.crt --reload 
```

## Docker build

To rebuild the Docker container:

```bash
docker build --no-cache docker -t ghcr.io/janeliascicomp/zarrcade:latest
docker push ghcr.io/janeliascicomp/zarrcade:latest
```

## Attributions

<https://www.iconsdb.com/black-icons/copy-link-icon.html>
