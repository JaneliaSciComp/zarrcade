import os
from functools import cache
from typing import Tuple, Sequence, Iterator, Protocol
from urllib.parse import urlparse
from dataclasses import dataclass

import fsspec
from loguru import logger


class FilestoreResolver:
    """ Resolves a URI into an fsspec filesystem and a web-accessible URL.
    """

    uri: str
    """ User provided URI
    """

    fs: fsspec.filesystem
    """ Filesystem for the URI
    """

    fsroot: str
    """ Root path of the filesystem
    """

    web_url: str
    """ Web-accessible URL for the filestore.
    """

    def __init__(self, uri: str):
        self.uri = uri
        logger.debug(f"Data URL: {self.uri}")

        pu = urlparse(uri)
        if pu.scheme in ['http','https'] and pu.netloc.endswith('.s3.amazonaws.com'):
            # Convert S3 HTTP URLs (which do not support list operations) back to S3 REST API
            self.fs = fsspec.filesystem('s3')
            self.fsroot = 's3://' + pu.netloc.split('.')[0] + pu.path
            self.web_url = uri
        else:
            self.fs = fsspec.filesystem(pu.scheme)
            self.fsroot = pu.netloc + pu.path
            if pu.scheme in ['s3']:
                self.web_url = f"https://{pu.netloc}.s3.amazonaws.com{pu.path}"
            else:
                self.web_url = None


@cache
def get_resolver(uri: str):
    return FilestoreResolver(uri)


class Filestore(Protocol):
    """
    Interface for accessing files.
    """
    def get_store(self, uri):
        """Returns a fsspec store for the given URI."""
        raise NotImplementedError()

    def get_absolute_path(self, uri):
        """Returns the full absolute path to the given URI."""
        raise NotImplementedError()

    def get_url(self, uri):
        """Returns the full URL to the given URI."""
        raise NotImplementedError()
    
    def exists(self, uri):
        """Returns true if a file or folder exists at the given URI."""
        raise NotImplementedError()

    def open(self, uri):
        """Opens the file at the given URI and returns
        the file handle."""
        raise NotImplementedError()

    def get_size(self, uri):
        """Returns the size of the file at the given URI."""
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

    def get_url(self, relative_path):
        """Returns the full URL to the given path."""
        if self.resolver.web_url:
            return os.path.join(self.resolver.web_url, relative_path)
        else:
            return None

    def exists(self, relative_path):
        """Returns true if a file or folder exists at the given relative path."""
        path = self.get_absolute_path(relative_path)
        return self.resolver.fs.exists(path)

    def open(self, relative_path):
        """Opens the file at the given relative path and returns
        the file handle."""
        path = self.get_absolute_path(relative_path)
        return self.resolver.fs.open(path)

    def get_size(self, relative_path):
        """Returns the size of the file at the given relative path."""
        path = self.get_absolute_path(relative_path)
        info = self.resolver.fs.info(path)
        return info['size']

    def get_children(self, relative_path):
        """Returns the children of the given relative path."""
        path = self.get_absolute_path(relative_path)
        children = []
        for child in self.resolver.fs.ls(path, detail=True):
            abspath = child['name']
            relpath = os.path.relpath(abspath, self.resolver.fsroot)
            children.append({
                'path': relpath,
                'name': os.path.basename(relpath),
                'type': child['type']
            })
        return children
    

class AbsoluteFilestore(Filestore):
    """Filestore containing images. May be on a local filesystem,
    or any remote filesystem supported by FSSPEC.
    """
    def get_store(self, uri):
        """Returns a fsspec store for the given relative path."""
        resolver = self.get_resolver(uri)
        root = os.path.join(resolver.fsroot, uri)
        return resolver.fs.get_mapper(root)

    def get_absolute_path(self, uri):
        """Returns the full absolute path to the given path."""
        return uri

    def get_url(self, uri):
        """Returns the full URL to the given path."""
        resolver = self.get_resolver(uri)
        return resolver.web_url

    def exists(self, uri):
        """Returns true if a file or folder exists at the given relative path."""
        resolver = self.get_resolver(uri)
        return resolver.fs.exists(uri)

    def open(self, uri):
        """Opens the file at the given relative path and returns
        the file handle."""
        resolver = self.get_resolver(uri)
        return resolver.fs.open(uri)

    def get_size(self, uri):
        """Returns the size of the file at the given relative path."""
        resolver = self.get_resolver(uri)
        info = resolver.fs.info(uri)
        return info['size']

    def get_children(self, uri):
        """Returns the children of the given relative path."""
        resolver = self.get_resolver(uri)
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
def get_filestore(data_url: str = None) -> Filestore:
    if data_url is None:
        return AbsoluteFilestore(data_url=data_url)
    else:
        return RelativeFilestore(data_url=data_url)
