# Zarrcade 

![logoz@0 1x](https://github.com/user-attachments/assets/21e45ddf-f53b-4391-9014-e1cad0243e7e)

Zarrcade is a web application for easily browsing collections of [NGFF](https://github.com/ome/ngff) (e.g. OME-Zarr) images. Implements the following useful features:

* Automatic discovery of images on [any storage backend supported by fsspec](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations) including file system, AWS S3, Azure Blob, Google Cloud Storage, Dropbox, etc.
* Web gallery with convenient viewing links to compliant viewers
* Neuroglancer state generation for multichannel images
* File proxy for non-public storage backends
* Support for optional image thumbnails


# Getting Started

1. [Install miniforge](https://docs.conda.io/en/latest/miniforge.html) if you don't already have it.

2. Install the necessary dependencies: 

```bash
conda env create -f environment.yml
conda activate zarrcade
pip install neuroglancer  --no-dependencies
```

3. Convert your image(s) to OME-Zarr format:

```bash
bioformats2raw -w 128 -h 128 -z 64 --compression zlib /path/to/input.image /path/to/output.zarr
```

If you have many images to convert, we recommend using the [nf-omezarr](https://github.com/JaneliaSciComp/nf-omezarr) Nextflow pipeline to efficiently run bioformats2raw on a collection of images. This pipelinecan also let you scale the conversion to your compute resources (cluster, cloud, etc).

4. Import images and metadata into Zarrcade:

You can import images into Zarrcade using the provided command line script:

```bash
bin/import.py -r /root/data/dir
```

To add extra metadata about the images, you can pass a CSV file with the `-i` flag:

```bash
bin/import.py -r /root/data/dir -i input.csv
```

The CSV file's first column must be a relative path pointing to OME-Zarr images within the root data directory. The remaining columns can be any metadata to be searched and displayed within the gallery, e.g.:

```csv
Path,Line,Marker
relative/path/to/ome1.zarr,JKF6363,Blu
relative/path/to/ome2.zarr,JDH3562,Blu
```

5. Run the Zarrcade web application:

Start the development server, pointing it to your OME-Zarr data:

```bash
DATA_URL=/path/to/data uvicorn zarrcade.serve:app --host 0.0.0.0 --reload
```

If you are running the service remote, you'll need to use HTTPS. Just point Uvicorn to your certificate and set your BASE_URL:

```bash
BASE_URL=https://myserver.mydomain.org:8000 DATA_URL=/path/to/data uvicorn zarrcade.serve:app --host 0.0.0.0 \
    --ssl-keyfile certs/cert.key --ssl-certfile certs/cert.crt --reload 
```



To run the service locally using Docker, just point it at your OME-Zarr data:

```bash
docker run -it -v /path/to/data:/data -p 8000:8000 ghcr.io/janeliascicomp/zarrcade
```

This will index your data and make it browseable at [http://127.0.0.1:8000](http://127.0.0.1:8000).


## Production Deployment

If your server is running remotely it will need to use HTTPS in order to be able to accessible to the viewers. You'll need to provide a TLS certificate and a base URL for generating links to your server. This is possible with Uvicorn, but using an Nginx reverse proxy server is usually preferred. Furthermore, by default Zarrcade uses an in-memory Sqlite database. If you want to use something else, set the `DB_URL` variable to point to a SQL database.

You can do this using [Docker Compose](https://docs.docker.com/compose/). Make sure you have this installed on your system before proceeding.

First, create a `.env` file in the `./docker` folder. You can copy the template like this:

```bash
cd docker
cp env.template .env
```

Customize the `.env` file and then start the services:

```bash
docker compose up -d
```



## Development


## Testing

```bash
python -m pytest --cov=zarrcade --cov-report html -W ignore::DeprecationWarning
```

## Docker build

To rebuild the Docker container:

```bash
docker build --no-cache docker -t ghcr.io/janeliascicomp/zarrcade:latest
docker push ghcr.io/janeliascicomp/zarrcade:latest
```

## Attributions

* <https://www.iconsdb.com/black-icons/copy-link-icon.html>
* <https://www.veryicon.com/icons/education-technology/smart-campus-1/view-details-2.html>
