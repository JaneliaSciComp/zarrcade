# Deployment

## Remote deployment

If you are running the service on a remote server, you'll need to use HTTPS and tell Zarrcade how to address your server. You can point Uvicorn to your SSL certificate and set your `BASE_URL` like this:

```bash
BASE_URL=https://myserver.mydomain.org:8000 uvicorn zarrcade.serve:app --host 0.0.0.0 \
    --ssl-keyfile certs/cert.key --ssl-certfile certs/cert.crt --reload 
```

You can also set `BASE_URL` and other configuration options in the `settings.yaml` file. See the [configuration documentation](./docs/Configuration.md) for more details.


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
