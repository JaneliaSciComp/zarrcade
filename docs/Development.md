# Development Notes

## Testing

```bash
zarrcade test
```

## Building the Docker container

Run the Docker build, replacing `<version>` with your version number:

```bash
cd docker/
export VERSION=<version>
docker build . --build-arg GIT_TAG=$VERSION -t ghcr.io/janeliascicomp/zarrcade:$VERSION
```

## Pushing the Docker container

```bash
docker push ghcr.io/janeliascicomp/zarrcade:$VERSION
docker tag ghcr.io/janeliascicomp/zarrcade:$VERSION ghcr.io/janeliascicomp/zarrcade:latest
docker push ghcr.io/janeliascicomp/zarrcade:latest
```