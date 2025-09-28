# Deployment

## Configuration 

You can configure Zarrcade by editing the `settings.yaml` file, or by setting environment variables. Environment variables are named with the prefix `ZARRCADE_` and will override settings in the `settings.yaml` file. These settings affect both the CLI scripts (e.g. `import.py`) and the web service.

The following configuration options are available:

`title`: The site title displayed at the top of the page.

`collection`: Single collection mode. If this collection name is specified, the index page will redirect directly to this collection, and no other collection may be selected.

`log_level`: The logging level to use for the Zarrcade service. This can be `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Default: `INFO`

`base_url`: The base URL for the Zarrcade service. This is used to generate URLs for the images and other resources in the service. It's required when using the build-in file proxy. Default: `http://127.0.0.1:8000/`

`database`: The database settings:
* `db_url`: The URL of the database to use for the Zarrcade service. This can be a SQLite database, a PostgreSQL database, or other database supported by SQLAlchemy. Default: `sqlite:///database.db`
* `debug_sql`: If true, SQLAlchemy queries will be logged at the `DEBUG` level.

Example `settings.yaml` file:

```yaml
title: Zarrcade 

log_level: INFO

base_url: https://localhost:8888

database:
  url: sqlite:///database.db
  debug_sql: False
```

## Remote deployment

If you are running the service on a remote server, you'll need to use HTTPS and tell Zarrcade how to address your server. You can point Uvicorn to your SSL certificate and set your `ZARRCADE_BASE_URL` (it could also be set in the `settings.yaml` file):

```bash
ZARRCADE_BASE_URL=https://myserver.mydomain.org:8000 pixi run zarrcade start --host 0.0.0.0 \
    --ssl-keyfile certs/cert.key --ssl-certfile certs/cert.crt --reload 
```

You can also run Uvicorn directly for access to more options:

```bash
ZARRCADE_BASE_URL=https://myserver.mydomain.org:8000 uvicorn zarrcade.serve:app --host 0.0.0.0 \
    --ssl-keyfile certs/cert.key --ssl-certfile certs/cert.crt --proxy-headers
```


## Running with Docker

To run the service locally using Docker, simply start the container and mount your OME-Zarr data:

```bash
docker run -it -v /root/data/dir:/data -p 8000:8000 ghcr.io/janeliascicomp/zarrcade
```


## Production Deployment
 
Using an [Nginx](https://nginx.org) reverse proxy server is usually preferred for production deployments. You can run Nginx and Uvicorn using the [Docker Compose](https://docs.docker.com/compose/) configuration in the `./docker` folder. Make sure you have [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/) installed on your system before proceeding.

First, create a `.env` file in the `./docker` folder. You can copy the template like this:

```bash
cd docker
cp env.template .env
```

Customize the `.env` file and then start the services:

```bash
docker compose up -d
```
