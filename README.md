# Zarrcade 

![logoz@0 1x](https://github.com/user-attachments/assets/21e45ddf-f53b-4391-9014-e1cad0243e7e)

Zarrcade is a web application for easily browsing, searching, and visualizing collections of [OME-NGFF](https://github.com/ome/ngff) (i.e. OME-Zarr) images. It implements the following features:

* Automatic discovery of OME-Zarr images on [any storage backend supported by fsspec](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations) including file system, AWS S3, Azure Blob, Google Cloud Storage, Dropbox, etc.
* Web gallery with convenient viewing links to NGFF-compliant viewers
* Neuroglancer state generation for multichannel images
* Build-in file proxy for non-public storage backends
* Searchable/filterable metadata
* Support for image thumbnails


## Getting Started

### 1. Install miniforge

[Install miniforge](https://docs.conda.io/en/latest/miniforge.html) if you don't already have it.

### 2. Initialize the conda environment

```bash
conda env create -f environment.yml
conda activate zarrcade
```

### 3. Create OME-Zarr images

Convert your image(s) to OME-Zarr format, e.g. using bioformats2raw:

```bash
bioformats2raw -w 128 -h 128 -z 64 --compression zlib /path/to/input.image /path/to/output.zarr
```

If you have many images to convert, we recommend using the [nf-omezarr Nextflow pipeline](https://github.com/JaneliaSciComp/nf-omezarr) to efficiently run bioformats2raw on a collection of images. This pipeline also lets you scale the conversion processes to  your available compute resources (cluster, cloud, etc).

### 4. Import images and metadata into Zarrcade

You can import images into Zarrcade using the provided command line script:

```bash
bin/import.py -d /root/data/dir -c collection_name
```

By default, this will create MIPs and thumbnails for each image in a folder named `.zarrcade`, within the root data directory. You can change this location by setting the `--aux-path` parameter. You can disable the creation of MIPs and thumbnails by setting the `--no-aux` flag. The brightness of the MIPs can be adjusted using the `--p-lower` and `--p-upper` parameters.

To add extra metadata about the images, you can provide a CSV file with the `-i` flag:

```bash
bin/import.py -d /root/data/dir -c collection_name -i input.csv
```

The CSV file's first column must be a relative path to the OME-Zarr image within the root data directory. The remaining columns can be any metadata to be searched and displayed within the gallery, e.g.:

```csv
Path,Line,Marker
relative/path/to/ome1.zarr,JKF6363,Blu
relative/path/to/ome2.zarr,JDH3562,Blu
```

### 5. Run the Zarrcade web application

Start the development server, pointing it to your OME-Zarr data:

```bash
uvicorn zarrcade.serve:app --host 0.0.0.0 --reload
```

Your data will be indexed and browseable at [http://0.0.0.0:8000](http://0.0.0.0:8000).

## Deployment

### Remote deployment

If you are running the service on a remote server, you'll need to use HTTPS and tell Zarrcade how to address your server. You can point Uvicorn to your SSL certificate and set your BASE_URL:

```bash
BASE_URL=https://myserver.mydomain.org:8000 uvicorn zarrcade.serve:app --host 0.0.0.0 \
    --ssl-keyfile certs/cert.key --ssl-certfile certs/cert.crt --reload 
```

You can also set these variables in a `settings.yaml` file. 


### Running with Docker

To run the service locally using Docker, simply start the container and mount your OME-Zarr data:

```bash
docker run -it -v /root/data/dir:/data -p 8000:8000 ghcr.io/janeliascicomp/zarrcade
```

## Production Deployment
 
Using an Nginx reverse proxy server is usually preferred for production deployments. You can run both Nginx and Uvicorn using the [Docker Compose](https://docs.docker.com/compose/) configuration in the `./docker` folder. Make sure you have this installed on your system before proceeding.

First, create a `.env` file in the `./docker` folder. You can copy the template like this:

```bash
cd docker
cp env.template .env
```

Customize the `.env` file and then start the services:

```bash
docker compose up -d
```

## Testing

```bash
python -m pytest --cov=zarrcade --cov-report html -W ignore::DeprecationWarning
```

## Docker build

To rebuild and republish the Docker container:

```bash
docker build --no-cache docker -t ghcr.io/janeliascicomp/zarrcade:latest
docker push ghcr.io/janeliascicomp/zarrcade:latest
```

## Attributions

* <https://www.iconsdb.com/black-icons/copy-link-icon.html>
* <https://www.veryicon.com/icons/education-technology/smart-campus-1/view-details-2.html>
