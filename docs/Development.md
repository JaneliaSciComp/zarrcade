# Development Notes

## Testing

```bash
pixi run zarrcade test
```

## Building the Docker container

Run the Docker build and push to GHCR, replacing `<version>` with your version number:

```bash
cd docker/
export VERSION=<version>
docker buildx build --platform linux/amd64,linux/arm64 --build-arg GIT_TAG=$VERSION -t ghcr.io/janeliascicomp/zarrcade:$VERSION -t ghcr.io/janeliascicomp/zarrcade:latest --push .
```
