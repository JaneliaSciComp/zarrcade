# Development Notes

## Testing

```bash
python -m pytest --cov=zarrcade --cov-report html -W ignore::DeprecationWarning
```

## Docker build

To rebuild and republish the Docker container (replacing 'latest' with the desired tag):

```bash
docker build --no-cache docker -t ghcr.io/janeliascicomp/zarrcade:latest
docker push ghcr.io/janeliascicomp/zarrcade:latest
```
