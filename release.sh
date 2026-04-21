#!/bin/bash
# Build and push the Zarrcade Docker image to GHCR.
#
# Usage: ./release.sh <version>
#   e.g. ./release.sh 2.0.0
#
# Prereqs:
#   - docker login ghcr.io  (with a PAT that has write:packages scope)
#   - run from the repo root
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

VERSION=$1
IMAGE=ghcr.io/janeliascicomp/zarrcade

docker build -f docker/Dockerfile -t "${IMAGE}:${VERSION}" .
docker tag "${IMAGE}:${VERSION}" "${IMAGE}:latest"
docker push "${IMAGE}:${VERSION}"
docker push "${IMAGE}:latest"
