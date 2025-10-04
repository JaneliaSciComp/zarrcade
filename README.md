# Zarrcade 

![logoz@0 1x](https://github.com/user-attachments/assets/21e45ddf-f53b-4391-9014-e1cad0243e7e)

[![Python CI](https://github.com/JaneliaSciComp/zarrcade/actions/workflows/python-ci.yml/badge.svg)](https://github.com/JaneliaSciComp/zarrcade/actions/workflows/python-ci.yml)

Zarrcade makes it easy to generate simple web applications for browsing, searching, and visualizing collections of [OME-NGFF](https://github.com/ome/ngff) (i.e. OME-Zarr) images. It implements the following features:

* Automatic discovery of OME-Zarr images on [any storage backend supported by fsspec](https://filesystem-spec.readthedocs.io/en/latest/api.html#other-known-implementations) including file system, AWS S3, Azure Blob, Google Cloud Storage, Dropbox, etc.
* MIP/thumbnail generation
* Web-based MIP gallery with convenient viewing links to OME-Zarr-compatible viewers
* Searchable/filterable metadata and annotations
* Build-in file proxy for non-public storage backends
* Integration with the Allen Institute's [BioFile Finder](https://bff.allencell.org/)
* Integration with external file proxies (e.g. [x2s3](https://github.com/JaneliaSciComp/x2s3))

<img alt="Zarrcade screenshot" src="https://github.com/user-attachments/assets/57895e8f-b427-43d3-bd81-bae2acb449a7" />

## Prerequisites

### 1. Install pixi

[Install pixi](https://pixi.sh/latest/) if you don't already have it.

### 2. Clone this repo

```bash
git clone https://github.com/JaneliaSciComp/zarrcade.git
cd zarrcade
```

### 3. Initialize the pixi environment

```bash
pixi install
```

Now you can run the `pixi run zarrcade` command.


## Examples

To try a simple example, use one of following commands to import the example data before starting the server.

### Example 1: Discover all OME-Zarr images stored within a given location

This example runs Zarr discovery on an S3 bucket. The metadata file adds textual annotations for each image. 

```bash
pixi run zarrcade load examples/flyefish.yaml
pixi run zarrcade start
```

### Example 2: Import OME-Zarr images specified in a spreadsheet

In this example, absolute paths are provided to [Open Organelle](https://openorganelle.janelia.org/) Zarr images in the [metadata file](examples/openorganelle.tsv), along with absolute thumbnail paths.

```bash
pixi run zarrcade load examples/openorganelle.yaml
pixi run zarrcade start
```

## Loading your own data

### 1. Create OME-Zarr images

If your images are not already in OME-Zarr format, you will need to convert them, e.g. using bioformats2raw:

```bash
bioformats2raw -w 128 -h 128 -z 64 --compression zlib /path/to/input /path/to/zarr
```

If you have many images to convert, use the [nf-omezarr Nextflow pipeline](https://github.com/JaneliaSciComp/nf-omezarr) to efficiently run bioformats2raw on a collection of images. This pipeline also lets you scale the conversion processes to your available compute resources (cluster, cloud, etc).

### 2. Create YAML configuration for your data collection

There is [documentation](docs/Configuration.md) on creating collection settings files, or you can follow one of the [examples](examples/).


### 3. Import images and metadata into Zarrcade

You can import images into Zarrcade using the provided command line script:

```bash
pixi run zarrcade load path/to/mycollection.yaml
```

This will automatically create a local Sqlite database containing a Zarrcade **collection** named "mycollection" and populate it with information about the images in the specified directory. By default, this will also create MIPs and thumbnails for each image in `./static/.zarrcade` (unless your metadata file already contains thumbnail paths). 

Read more about the import options in the [Data Import](./docs/DataImport.md) section of the documentation.

### 4. Run the Zarrcade web application

Start the development server, pointing it to your OME-Zarr data:

```bash
pixi run dev-launch
```

This is equivalent to running Uvicorn like this:
```bash
pixi run uvicorn zarrcade.serve:app --port 8000 --reload
```

Your images and annotations will be browseable at [http://0.0.0.0:8000](http://0.0.0.0:8000). Read the documentation below for more details on how to configure the web UI and deploy the service in production.


## Documentation

* [Overview](./docs/Overview.md) - learn about the data model and overall architecture
* [Configuration](./docs/Configuration.md) - configure the Zarrcade service using settings.yaml or environment variables
* [Deployment](./docs/Deployment.md) - instructions for deploying the service with Docker and in production mode
* [Development Notes](./docs/Development.md) - technical notes for developers working on Zarrcade itself


## Known Limitations

* The `OmeZarrAgent` does not currently support the full OME-Zarr specification, and may fail with certain types of images. If you encounter an error with your data, please open an issue on the [Github repository](https://github.com/JaneliaSciComp/zarrcade/issues).


## Attributions

* <https://www.iconsdb.com/black-icons/copy-link-icon.html>
* <https://www.veryicon.com/icons/education-technology/smart-campus-1/view-details-2.html>
