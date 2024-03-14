
# NGFF Browse


Install the necessary packages using conda:
```
conda env create -f environment.yml
conda activate ngffbrowse
```

Run using Uvicorn:
```
uvicorn ngffbrowse:serve 
```


## Docker

To rebuild the Docker container:
```
docker build --no-cache docker -t ghcr.io/janeliascicomp/ngffbrowse:latest
docker push ghcr.io/janeliascicomp/ngffbrowse:latest
```




