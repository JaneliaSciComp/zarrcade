"""File storage abstraction layer supporting various backends."""

import os
from functools import cache
from typing import Protocol
from urllib.parse import urlparse

import fsspec
from s3fs.core import S3FileSystem
from loguru import logger


class FilestoreResolver:
    """Resolves a URI into an fsspec filesystem and a web-accessible URL."""

    uri: str
    """User provided URI"""

    fs: fsspec.filesystem
    """Filesystem for the URI"""

    fsroot: str
    """Root path of the filesystem"""

    web_url: str
    """Web-accessible URL for the filestore."""

    def __init__(self, uri: str):
        self.uri = uri
        pu = urlparse(uri)
        if pu.scheme in ['http', 'https'] and pu.netloc.endswith('.s3.amazonaws.com'):
            # Convert S3 HTTP URLs (which do not support list operations) back to S3 REST API
            self.fs = fsspec.filesystem('s3')
            self.fsroot = 's3://' + pu.netloc.split('.')[0] + pu.path
            self.web_url = uri
            logger.info(f"Resolved S3 bucket {uri} to {self.fsroot} and {self.web_url}")
        elif pu.scheme in ['http', 'https'] and pu.netloc.startswith('s3.'):
            # Detect S3-compatible servers
            self.fs = S3FileSystem(anon=True, client_kwargs={'endpoint_url': f"{pu.scheme}://{pu.netloc}"})
            self.fsroot = pu.path
            self.web_url = uri
            logger.info(f"Resolved S3-compatible URL {uri} to {self.fsroot} and {self.web_url}")
        else:
            self.fs = fsspec.filesystem(pu.scheme)
            self.fsroot = pu.netloc + pu.path
            if pu.scheme in ['s3']:
                self.web_url = f"https://{pu.netloc}.s3.amazonaws.com{pu.path}"
            else:
                self.web_url = None
            logger.info(f"Resolved {pu.scheme} server {pu.netloc} to {self.fsroot} and {self.web_url}")


@cache
def get_resolver(uri: str):
    return FilestoreResolver(uri)


class Filestore(Protocol):
    """Interface for accessing files."""

    def get_store(self, uri):
        """Returns a fsspec store for the given URI."""
        raise NotImplementedError()

    def get_absolute_path(self, uri):
        """Returns the full absolute path to the given URI."""
        raise NotImplementedError()

    def get_children(self, uri):
        """Returns the children of the given URI."""
        raise NotImplementedError()


class RelativeFilestore(Filestore):
    """Filestore containing images. May be on a local filesystem,
    or any remote filesystem supported by FSSPEC.
    """

    def __init__(self, data_url: str = None):
        self.data_url = data_url
        self.resolver = get_resolver(data_url)

    def get_store(self, relative_path):
        """Returns a fsspec store for the given relative path."""
        root = os.path.join(self.resolver.fsroot, relative_path)
        return self.resolver.fs.get_mapper(root)

    def get_absolute_path(self, relative_path):
        """Returns the full absolute path to the given path."""
        return os.path.join(self.resolver.fsroot, relative_path)

    def get_children(self, relative_path):
        """Returns the children of the given relative path."""
        path = self.get_absolute_path(relative_path)
        children = []
        for child in self.resolver.fs.ls(path, detail=True):
            abspath = child['name']
            if not abspath.startswith('/'):
                abspath = '/' + abspath
            relpath = os.path.relpath(abspath, self.resolver.fsroot)
            child = {
                'path': relpath,
                'name': os.path.basename(relpath),
                'type': child['type']
            }
            children.append(child)
        return children


class AbsoluteFilestore(Filestore):
    """Filestore containing images. May be on a local filesystem,
    or any remote filesystem supported by FSSPEC.
    """

    def get_store(self, uri):
        """Returns a fsspec store for the given relative path."""
        resolver = get_resolver(uri)
        return resolver.fs.get_mapper(uri)

    def get_absolute_path(self, uri):
        """Returns the full absolute path to the given path."""
        return uri

    def get_children(self, uri):
        """Returns the children of the given relative path."""
        resolver = get_resolver(uri)
        children = []
        for child in resolver.fs.ls(uri, detail=True):
            abspath = child['name']
            relpath = os.path.relpath(abspath, resolver.fsroot)
            children.append({
                'path': relpath,
                'name': os.path.basename(relpath),
                'type': child['type']
            })
        return children


@cache
def get_filestore(data_url=None) -> Filestore:
    if data_url is None:
        return AbsoluteFilestore()
    else:
        return RelativeFilestore(data_url=data_url)
