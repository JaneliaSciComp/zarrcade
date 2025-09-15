#!/bin/bash
export VERSION=$1
docker build . --build-arg GIT_TAG=$VERSION -t ghcr.io/janeliascicomp/zarrcade:$VERSION \
    && docker push ghcr.io/janeliascicomp/zarrcade:$VERSION \
    && docker tag ghcr.io/janeliascicomp/zarrcade:$VERSION ghcr.io/janeliascicomp/zarrcade:latest \
    && docker push ghcr.io/janeliascicomp/zarrcade:latest

