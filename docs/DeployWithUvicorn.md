# Deploying with Uvicorn

Zarrcade may be configured to run everything to in single container. Compared to [Deploying with Docker Compose](DeployWithCompose.md), this method is simpler and faster, but may not provide all the bells and whistles you might want in a production web application.

To run the FastAPI application fronted with Uvicorn, using HTTPS and an external database, you can do this:

```bash
docker run -it -v /path/to/data:/data \
    -v /path/to/keyfile:/certs/keyfile \
    -v /path/to/certfile:/certs/certfile \
    -e KEY_FILE=/certs/keyfile \
    -e CERT_FILE=/certs/certfile \
    -e BASE_URL=https://yourdomainname.org \
    -e DB_URL=sqlite:///database.db \
    ghcr.io/janeliascicomp/zarrcade
```

Note that your database will be ephemeral since it is hosted inside the container. Externalize your database with a volume if you'd like it to persist between restarts.

