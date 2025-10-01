#!/usr/bin/env python3
"""
Import data into the Zarrcade database by walking a filesystem and discovering Zarrs. 
Optionally imports metadata and 2d thumbnails.
"""
import os
import re
import unicodedata
import argparse
from functools import partial

import pandas as pd
from urllib.parse import urlparse
from loguru import logger

from zarrcade import Database, get_filestore
from zarrcade.settings import get_settings
from zarrcade.agents import yield_images
from zarrcade.agents.omezarr import OmeZarrAgent
from zarrcade.thumbnails import make_mip_from_zarr, make_thumbnail
from zarrcade.collection import load_collection_settings

# Adapted from https://github.com/django/django/blob/main/django/utils/text.py
def slugify(value, allow_unicode=False):
    """
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Convert to lowercase. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    value = re.sub(r"[^\w\s-]", "", value.lower())
    return re.sub(r"[-\s]+", "_", value).strip("-_")


def get_all_images(db, collection_name):
    return db.get_dbimages(collection=collection_name, page_size=0)['images']
        

def load(settings_path, args):
    settings = get_settings()
    local_fs = get_filestore()
    
    # Connect to the database
    db_url = str(settings.database.url)
    logger.info(f"Database URL is {db_url}")
    db = Database(db_url)

    if db.collection_map:
        logger.info("Collections:")
        for key, value in db.collection_map.items():
            logger.info(f"  {key} ({value.settings_path})")
            collection_name = key
            column_map = db.get_column_map(collection_name)
            for key, value in column_map.items():
                logger.info(f"    {key}: {value}")

    # extract the file name
    collection_name = slugify(os.path.splitext(os.path.basename(settings_path))[0])

    # Read the collection settings
    collection_settings = load_collection_settings(settings_path)

    # Set up the collection
    db.add_collection(collection_name, settings_path)

    thumbnail_column = None
    metadata_path = collection_settings.metadata_file
    if metadata_path and not os.path.isabs(metadata_path):
        # Make metadata path relative to collection settings file location
        settings_dir = os.path.dirname(os.path.abspath(settings_path))
        metadata_path = os.path.join(settings_dir, metadata_path)

    if metadata_path:
        
        # Read the metadata and set up the columns
        logger.info(f"Reading {metadata_path}")

        # Use sep=None to automatically detect the delimiter
        # Sometimes we need to use encoding='ISO-8859-1' here to avoid UnicodeDecodeError
        df = pd.read_csv(metadata_path, sep=None, engine='python')
        logger.info(f"Parsed {df.shape[0]} rows from metadata CSV")
    
        # Assume the first column is the image path
        path_column_name = df.columns[0]
        logger.info(f"The first column '{path_column_name}' will be treated as the image URI")

        # Skip the first column which is the path
        columns = df.columns[1:]

        # Slugify the column names and add them to the database
        for original_name in columns:
            if "thumbnail" in original_name.lower():
                logger.info(f"Found thumbnail URL column: {original_name}")
                thumbnail_column = original_name
                continue

            # Prepend "c" in case the column label starts with a number
            db_name = 'c_'+slugify(original_name)
            db.add_metadata_column(collection_name, db_name, original_name)

        # Insert the metadata
        logger.info("Inserting metadata...")
                
        reverse_column_map = db.get_reverse_column_map(collection_name)
        new_objs = []
        for _, row in df.iterrows():
            path = row[path_column_name].rstrip('/')
            new_obj = {reverse_column_map[c]: row[c] for c in columns if c != thumbnail_column}
            new_obj['path'] = path
            if thumbnail_column:
                new_obj['thumbnail_path'] = row[thumbnail_column]
            new_objs.append(new_obj)

        inserted, updated = db.add_image_metadata(collection_name, new_objs)
        logger.info(f"Inserted {inserted} rows of metadata")
        logger.info(f"Updated {updated} rows of metadata")

    # Load the images
    if not args.skip_image_load:
        if collection_settings.discovery:
            data_url = str(collection_settings.discovery.data_url)
            fs = get_filestore(data_url)
            logger.info(f"Discovering images at URL: {data_url}")
            generator = partial(yield_images, fs, agents=[OmeZarrAgent()], exclude_paths=collection_settings.discovery.exclude_paths)
            db.persist_images(collection_name, generator,
                only_with_metadata=args.only_with_metadata)
        else:
            logger.info(f"Loading images for collection {collection_name}")

            # Get all images from metadata
            def generate_images():    
                for dbimage_metadata in db.get_all_image_metadata(collection_name):
                    # Split path into zarr path and any remaining path components
                    zarr_path = dbimage_metadata.path.split('.zarr')[0] + '.zarr'
                    group_path = dbimage_metadata.path[len(zarr_path):]
                    logger.info(f"Looking for image under URI: {zarr_path} / {group_path}")
                    agent = OmeZarrAgent()
                    try:
                        image = agent.get_image(local_fs, zarr_path, group_path)
                        yield (zarr_path, image)
                    except Exception as e:
                        logger.exception(f"Error encoding image at {zarr_path}/{group_path}: {e}")
                    
            db.persist_images(collection_name, generate_images, 
                            only_with_metadata=args.only_with_metadata)

    if not args.no_aux and thumbnail_column is None:
        # Load aux images and thumbnails
        logger.info("Loading thumbnails...")

        def create_parent_dirs(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)

        def get_aux_path(image_path, filename):
            # If image_path is a URI, extract just the hostname and path components
            if '://' in image_path:
                parsed = urlparse(image_path)
                # Combine hostname and path, removing any double slashes
                image_path = os.path.join(parsed.netloc, parsed.path.lstrip('/'))
            zarr_name, _ = os.path.splitext(image_path)
            aux_path = os.path.join('static', args.aux_path, zarr_name, filename)
            return aux_path

        thumb_fs = local_fs
        if collection_settings.discovery:
            data_url = str(collection_settings.discovery.data_url)
            thumb_fs = get_filestore(data_url)

        for dbimage in get_all_images(db, collection_name):
            logger.info(f"Processing {dbimage.path}")
            metadata = dbimage.image_metadata
            image = dbimage.get_image()
            updated_obj = {}
            aux_path = None

            if args.aux_image_name and (not metadata or not metadata.aux_image_path):
                aux_path = get_aux_path(dbimage.path, args.aux_image_name)
                logger.info(f"Checking for auxiliary path: {aux_path}")

                if thumb_fs.exists(aux_path):
                    logger.info(f"Found auxiliary file: {aux_path}")
                    updated_obj['aux_image_path'] = aux_path.replace('static/', '')
                elif args.skip_thumbnail_creation:
                    logger.info(f"Skipping auxiliary file creation: {aux_path}")
                elif not aux_path.startswith('s3://'):
                    logger.info(f"Creating auxiliary file: {aux_path}")
                    create_parent_dirs(aux_path)
                    store = fs.get_store(dbimage.image_path)
                    colors = []
                    for channel in image.channels:
                        colors.append(channel['color'])
                    try:
                        make_mip_from_zarr(store, aux_path, p_lower=args.p_lower, p_upper=args.p_upper, colors=colors)
                        logger.info(f"Wrote {aux_path}")
                        updated_obj['aux_image_path'] = aux_path.replace('static/', '')
                    except Exception as e:
                        logger.exception(f"Error making auxiliary image at {aux_path}: {e}")
                        aux_path = None

            if args.thumbnail_name and (not metadata or not metadata.thumbnail_path):
                tb_path = get_aux_path(dbimage.path, args.thumbnail_name)

                if thumb_fs.exists(tb_path):
                    logger.trace(f"Found thumbnail: {tb_path}")
                    updated_obj['thumbnail_path'] = tb_path.replace('static/', '')
                elif args.skip_thumbnail_creation:
                    logger.trace(f"Skipping thumbnail creation: {tb_path}")
                elif aux_path:
                    logger.trace(f"Creating thumbnail: {tb_path}")
                    create_parent_dirs(tb_path)
                    make_thumbnail(aux_path, tb_path)
                    logger.info(f"Wrote {tb_path}")
                    updated_obj['thumbnail_path'] = tb_path.replace('static/', '')
                else:
                    logger.trace(f"Cannot make thumbnail for {path} without aux image")

            if updated_obj:
                if not metadata:
                    # Metadata doesn't exist, create it
                    inserted, updated = db.add_image_metadata(collection_name, [{
                        'path': dbimage.path,
                        **updated_obj
                    }])
                    if inserted==1:
                        logger.info(f"Inserted metadata for {dbimage.path}")
                    else:
                        logger.error(f"Error inserting metadata for {dbimage.path}")
                else:
                    # Metadata exists, update it
                    db.update_image_metadata(collection_name, metadata.id, updated_obj)
                    logger.info(f"Updated metadata for {dbimage.path}")

        # Update the images with the new metadata ids if ncessary
        # This happens if we don't have user provided metadata and the metadatas
        # were created at the thumbnail generation step.
        path_to_metadata_id = db.get_path_to_metadata_id_map(collection_name)
        for dbimage in get_all_images(db, collection_name):
            if dbimage.image_metadata_id is None:
                if dbimage.path in path_to_metadata_id:
                    dbimage.image_metadata_id = path_to_metadata_id[dbimage.path]
                    db.update_image(dbimage)
                    logger.info(f"Updated image {dbimage.path} with metadata id {dbimage.image_metadata_id}")
                elif dbimage.image_path in path_to_metadata_id:
                    dbimage.image_metadata_id = path_to_metadata_id[dbimage.image_path]
                    db.update_image(dbimage)
                    logger.info(f"Updated image {dbimage.path} with metadata id {dbimage.image_metadata_id}")
                else:
                    logger.warning(f"No metadata found for {dbimage.path} or {dbimage.image_path}")

    logger.info("Database initialization complete.")
