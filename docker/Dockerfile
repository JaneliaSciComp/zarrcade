FROM ubuntu:22.04
ARG GIT_TAG=main

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install pixi
RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH="/root/.pixi/bin:$PATH"

WORKDIR /app
RUN git clone --branch $GIT_TAG --depth 1 https://github.com/JaneliaSciComp/zarrcade.git

WORKDIR /app/zarrcade
RUN pixi install

ENTRYPOINT [ "/app/zarrcade/docker/entrypoint.sh" ]
