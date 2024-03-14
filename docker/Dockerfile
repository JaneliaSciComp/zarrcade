FROM condaforge/mambaforge
ARG GIT_TAG=main

WORKDIR /app
RUN git clone --branch $GIT_TAG --depth 1 https://github.com/krokicki/ngffbrowse.git

WORKDIR /app/ngffbrowse
RUN mamba env create -f environment.yml \
    && mamba clean --all -y

ENTRYPOINT [ "/app/ngffbrowse/docker/entrypoint.sh" ]
