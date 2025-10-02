# check=skip=JSONArgsRecommended
FROM ghcr.io/prefix-dev/pixi:0.41.4 AS build
ARG GIT_TAG=main

RUN apt-get update && apt-get install -y git

WORKDIR /app
RUN git clone --branch $GIT_TAG --depth 1 https://github.com/JaneliaSciComp/zarrcade.git

WORKDIR /app/zarrcade
# install dependencies to `/app/.pixi/envs/default`
# use `--locked` to ensure the lockfile is up to date with pixi.toml
RUN pixi install --locked -e default \
    # create the shell-hook bash script to activate the environment
    && pixi shell-hook -e default -s bash > /shell-hook \
    && echo "#!/bin/bash" > /app/entrypoint.sh \
    && cat /shell-hook >> /app/entrypoint.sh \
    # extend the shell-hook script to run the command passed to the container
    && echo 'exec "$@"' >> /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

FROM ubuntu:24.04 AS production
LABEL org.opencontainers.image.source="https://github.com/JaneliaSciComp/zarrcade"

ENV HOST=0.0.0.0
ENV PORT=8000
ENV NUM_WORKERS=8

WORKDIR /app/zarrcade
COPY --from=build /app /app

EXPOSE $PORT
ENTRYPOINT [ "/app/entrypoint.sh" ]
CMD uvicorn zarrcade.serve:app --host ${HOST} --port ${PORT} --workers ${NUM_WORKERS} --forwarded-allow-ips='*' --proxy-headers
