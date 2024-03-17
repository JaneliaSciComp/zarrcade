
# NGFF Browse

## Development

Install the necessary packages using conda:

```bash
conda env create -f environment.yml
conda activate ngffbrowse
pip install neuroglancer  --no-dependencies
```

Run using Uvicorn:

```bash
DATA_URL=/path/to/data uvicorn ngffbrowse.serve:app --reload
```

## Docker build

To rebuild the Docker container:

```bash
docker build --no-cache docker -t ghcr.io/janeliascicomp/ngffbrowse:latest
docker push ghcr.io/janeliascicomp/ngffbrowse:latest
```

## Attributions

<https://www.iconsdb.com/black-icons/copy-link-icon.html>
