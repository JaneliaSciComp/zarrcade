FROM condaforge/mambaforge
ARG GIT_TAG=main

WORKDIR /app
RUN git clone --branch $GIT_TAG --depth 1 https://github.com/krokicki/zarrcade.git

WORKDIR /app/zarrcade
RUN mamba env create -f environment.yml \
    && mamba clean --all -y \
    && mamba run -n zarrcade pip install neuroglancer --no-dependencies

ENTRYPOINT [ "/app/zarrcade/docker/entrypoint.sh" ]
