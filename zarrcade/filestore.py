import os
from typing import Iterator
from urllib.parse import urlparse

import fsspec
import s3fs
from loguru import logger

from zarrcade.model import Image
from zarrcade.images import yield_ome_zarrs, yield_images


def get_fs(url:str):
    """ Parsers the given URL and returns an fsspec filesystem along with
        a root path and web-accessible URL.
    """
    pu = urlparse(url)
    if pu.scheme in ['http','https'] and pu.netloc.endswith('.s3.amazonaws.com'):
        # Convert S3 HTTP URLs (which do not support list operations) back to S3 REST API
        fs = fsspec.filesystem('s3')
        fsroot = pu.netloc.split('.')[0] + pu.path
        web_url = url
    else:
        fs = fsspec.filesystem(pu.scheme)
        fsroot = pu.netloc + pu.path
        if pu.scheme in ['s3']:
            web_url = f"https://{pu.netloc}.s3.amazonaws.com{pu.path}"
        else:
            web_url = None
    return fs, fsroot, web_url


class Filestore:
    """ Filestore containing images. May be on a local filesystem, 
        or any remote filesystem supported by FSSPEC.
    """

    def __init__(self, data_url):
        self.fs, self.fsroot, self.url = get_fs(data_url)
        logger.info(f"Filesystem root is {self.fsroot}")
        if self.url:
            logger.info(f"Web-accessible url root is {self.url}")
        else:
            logger.info("Filesystem is not web-accessible and will be proxied")

        # Ensure dir ends in a path separator
        self.fsroot_dir = os.path.join(self.fsroot, '')
        logger.trace(f"Filesystem dir is {self.fsroot_dir}")


    def yield_images(self) -> Iterator[Image]:
        """ Discover images in the filestore 
            and persist them in the given database.
        """
        logger.info(f"Discovering images in {self.fsroot}")
        for relative_path in yield_ome_zarrs(self):
            logger.trace(f"Found images in {relative_path}")
            absolute_path = os.path.join(self.fsroot_dir, relative_path)
            # TODO: move this logic somewhere else
            if isinstance(self.fs, s3fs.core.S3FileSystem):
                absolute_path = 's3://' + absolute_path

            logger.trace(f"Reading images in {absolute_path}")
            for image in yield_images(absolute_path, relative_path):
                yield image


    def is_local(self):
        """ Returns true if the current filestore is a local filesystem, 
            false otherwise.
        """
        return isinstance(self.fs, fsspec.implementations.local.LocalFileSystem)


    def get_absolute_path(self, relative_path):
        """ Returns the full absolute path to the given path.
        """
        return os.path.join(self.fsroot, relative_path)

 
    def exists(self, relative_path):
        """ Returns true if a file or folder exists at the given relative path.
        """
        path = self.get_absolute_path(relative_path)
        return self.fs.exists(path)


    def open(self, relative_path):
        """ Opens the file at the given relative path and returns
            the file handle.
        """
        path = self.get_absolute_path(relative_path)
        return self.fs.open(path)


    def get_size(self, relative_path):
        """ Returns the size of the file at the given relative path.
        """
        path = self.get_absolute_path(relative_path)
        info = self.fs.info(path)
        return info['size']


    def get_children(self, relative_path):
        """ Returns the children of the given relative path.
        """
        path = self.get_absolute_path(relative_path)
        children = []
        for child in self.fs.ls(path, detail=True):
            abspath = child['name']
            relpath = os.path.relpath(abspath, self.fsroot)
            children.append({
                'path': relpath,
                'name': os.path.basename(relpath),
                'type': child['type']
            })
        return children