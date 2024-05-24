import os
import fsspec
import s3fs

from loguru import logger

from zarrcade.images import yield_ome_zarrs, yield_images, get_fs


class Filestore:
    """ Filestore containing images. May be on a local filesystem, 
        or any remote filesystem supported by FSSPEC.
    """

    def __init__(self, data_url):
        self.fs, self.fsroot = get_fs(data_url)
        logger.debug(f"Filesystem root is {self.fsroot}")

        # Ensure dir ends in a path separator
        self.fsroot_dir = os.path.join(self.fsroot, '')
        logger.trace(f"Filesystem dir is {self.fsroot_dir}")


    def discover_images(self, db, only_with_metadata=False):
        """ Discover images in the filestore 
            and persist them in the given database.
        """
        logger.info(f"Discovering images in {self.fsroot}")
        # Temporarily cache relpath -> metadata id lookup table
        metadata_ids = db.get_relpath_to_metadata_id_map(self.fsroot)
        # Walk the storage root and populate the database
        count = 0
        for zarr_path in yield_ome_zarrs(self.fs, self.fsroot):
            logger.trace(f"Found images in {zarr_path}")
            relative_path = zarr_path.removeprefix(self.fsroot_dir)
            logger.trace(f"Relative path is {relative_path}")
            absolute_path = self.fsroot_dir + relative_path
            if isinstance(self.fs, s3fs.core.S3FileSystem):
                absolute_path = 's3://' + absolute_path

            logger.trace(f"Reading images in {absolute_path}")
            for image in yield_images(absolute_path, relative_path):

                if relative_path in metadata_ids:
                    metadata_id = metadata_ids[relative_path]
                else:
                    metadata_id = None

                if metadata_id or not only_with_metadata:
                    logger.debug(f"Persisting {image}")
                    db.persist_image(self.fsroot,
                                relpath=relative_path,
                                dataset=image.id.removeprefix(relative_path),
                                image=image,
                                metadata_id=metadata_id)
                    count += 1

        logger.info(f"Persisted {count} images to the database")


    def is_local(self):
        """ Returns true if the current filestore is a local filesystem, 
            false otherwise.
        """
        return isinstance(self.fs, fsspec.implementations.local.LocalFileSystem)


    def exists(self, relative_path):
        """ Returns true if a file or folder exists at the given relative path.
        """
        path = os.path.join(self.fsroot, relative_path)
        return self.fs.exists(path)


    def open(self, relative_path):
        """ Opens the file at the given relative path and returns
            the file handle.
        """
        path = os.path.join(self.fsroot, relative_path)
        return self.fs.open(path)


    def get_size(self, relative_path):
        """ Returns the size of the file at the given relative path.
        """
        path = os.path.join(self.fsroot, relative_path)
        info = self.fs.info(path)
        return info['size']
