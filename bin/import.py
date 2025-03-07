#!/usr/bin/env python3
"""
Import data into the Zarrcade database by walking a filesystem and discovering Zarrs. 
Optionally imports metadata and 2d thumbnails.
"""

import sys
sys.path.insert(0, '.')
sys.path.insert(0, '..')

import os
import re
import unicodedata
import argparse
import pandas as pd
from functools import partial
from loguru import logger

from zarrcade import Database, get_filestore
from zarrcade.settings import get_settings
from zarrcade.agents import yield_images
from zarrcade.agents.omezarr import OmeZarrAgent
from zarrcade.thumbnails import make_mip_from_zarr, make_thumbnail

EXCLUDE_PATHS = ['.zarrcade']


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

        
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('-d', '--data-url', type=str,
        help='URL to the root of the data.', required=True)
    parser.add_argument('-c', '--collection-name', type=str,
        help='Short name for collection. Only lowercase letters and underscores allowed.', required=True)
    parser.add_argument('-n', '--collection-label', type=str,
        help='Label for collection.', required=False)
    parser.add_argument('-m', '--metadata-path', type=str,
        help='Path to the CSV file containing additional metadata')
    parser.add_argument('-x', '--no-aux', action=argparse.BooleanOptionalAction, default=False,
        help="Don't create auxiliary images or thumbnails.")
    parser.add_argument('-a', '--aux-path', type=str, default=".zarrcade",
        help='Local path to the folder for auxiliary images.')
    parser.add_argument('--skip-image-load', action=argparse.BooleanOptionalAction, default=False,
        help="Skip loading images from the data directory.")
    parser.add_argument('--skip-thumbnail-creation', action=argparse.BooleanOptionalAction, default=False,
        help="Skip creating thumbnails if they do not already exist.")
    parser.add_argument('--aux-image-name', type=str, default='zmax.png',
        help='Filename of the main auxiliary image.')
    parser.add_argument('--thumbnail-name', type=str, default='zmax_sm.jpg',
        help='Filename of the thumbnail image for the gallery view.')
    parser.add_argument('--p-lower', type=int, default=0,
        help='Lower percentile for brightness adjustment.')
    parser.add_argument('--p-upper', type=int, default=90,
        help='Upper percentile for brightness adjustment.')
    parser.add_argument('--only-with-metadata', action=argparse.BooleanOptionalAction, default=False,
        help="Only load images for which metadata is provided?")
    parser.add_argument('--exclude', type=str, nargs='+', default=[],  # This allows multiple --exclude arguments
        help='Paths to exclude (can be used multiple times). This supports git-style wildcards like **/*.zarrcade'
    )

    args = parser.parse_args()
    data_url = args.data_url
    collection_name = slugify(args.collection_name)
    metadata_path = args.metadata_path

    # Connect to the database
    settings = get_settings()

    # Connect to the filestore
    logger.info(f"Data URL is {data_url}")
    exclude_paths = EXCLUDE_PATHS + settings.exclude_paths + args.exclude
    fs = get_filestore(data_url, exclude_paths=tuple(exclude_paths))

    # Connect to the database
    db_url = str(settings.database.url)
    logger.info(f"Database URL is {db_url}")
    db = Database(db_url)

    logger.info("Current collections:")
    for key, value in db.collection_map.items():
        logger.info(f"  {key}: {value.data_url}")

    logger.info("Current metadata columns:")
    for key, value in db.column_map.items():
        logger.info(f"  {key}: {value}")

    # Set up the collection
    db.add_collection(collection_name, args.collection_label or collection_name, data_url)


    if metadata_path:
        # Read the metadata and set up the columns
        logger.info(f"Reading {metadata_path}")
        df = pd.read_csv(metadata_path)
        path_column_name = df.columns[0]
        logger.info(f"Parsed {df.shape[0]} rows from metadata CSV")
        logger.info(f"The first column '{path_column_name}' will be treated as the relative path")

        # Skip the first column which is the path
        columns = df.columns[1:]

        # Slugify the column names and add them to the database
        for original_name in columns:
            # Prepend "c" in case the column label starts with a number
            db_name = 'c_'+slugify(original_name)
            db.add_metadata_column(db_name, original_name)

        # Insert the metadata
        logger.info("Inserting metadata...")
                
        new_objs = []
        for _, row in df.iterrows():
            path = row[path_column_name]
            new_obj = {db.reverse_column_map[c]: row[c] for c in columns}
            new_obj['collection'] = collection_name
            new_obj['path'] = path
            new_objs.append(new_obj)

        inserted, updated = db.add_image_metadata(new_objs)
        logger.info(f"Inserted {inserted} rows of metadata")
        logger.info(f"Updated {updated} rows of metadata")

    # Load the images
    if not args.skip_image_load:
        logger.info("Loading images...")
        generator = partial(yield_images, fs, agents=[OmeZarrAgent()])
        db.persist_images(collection_name, generator,
            only_with_metadata=args.only_with_metadata)

    if not args.no_aux:
        # Load aux images and thumbnails
        logger.info("Loading thumbnails...")

        def create_parent_dirs(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)

        def get_aux_path(zarr_path, filename):
            zarr_name, _ = os.path.splitext(zarr_path)
            aux_path = os.path.join(args.aux_path, zarr_name, filename)
            return aux_path

        images = db.get_dbimages(collection=collection_name, page_size=0)['images']
        for dbimage in images:
            logger.info(f"Processing {dbimage.path}")
            metadata = dbimage.image_metadata
            image = dbimage.get_image()
            updated_obj = {}
            aux_path = None
            
            logger.debug(f"aux_image_name: {args.aux_image_name}")
            logger.debug(f"Metadata: {metadata}")
            if metadata:
                logger.debug(f"Metadata aux_image_path: {metadata.aux_image_path}")
            
            if args.aux_image_name and (not metadata or not metadata.aux_image_path):
                aux_path = get_aux_path(dbimage.path, args.aux_image_name)
                logger.debug(f"Auxiliary path: {aux_path}")

                if fs.exists(aux_path):
                    logger.trace(f"Found auxiliary file: {aux_path}")
                    updated_obj['aux_image_path'] = aux_path
                elif args.skip_thumbnail_creation:
                    logger.trace(f"Skipping auxiliary file creation: {aux_path}")
                else:
                    logger.trace(f"Creating auxiliary file: {aux_path}")
                    create_parent_dirs(aux_path)
                    store = fs.get_store(dbimage.image_path)
                    colors = []
                    for channel in image.channels:
                        colors.append(channel['color'])
                    make_mip_from_zarr(store, aux_path, p_lower=args.p_lower, p_upper=args.p_upper, colors=colors)
                    logger.info(f"Wrote {aux_path}")
                    updated_obj['aux_image_path'] = aux_path

            if args.thumbnail_name and (not metadata or not metadata.thumbnail_path):
                tb_path = get_aux_path(dbimage.path, args.thumbnail_name)

                if fs.exists(tb_path):
                    logger.trace(f"Found thumbnail: {tb_path}")
                    updated_obj['thumbnail_path'] = tb_path
                elif args.skip_thumbnail_creation:
                    logger.trace(f"Skipping thumbnail creation: {tb_path}")
                elif aux_path:
                    logger.trace(f"Creating thumbnail: {tb_path}")
                    create_parent_dirs(tb_path)
                    make_thumbnail(aux_path, tb_path)
                    logger.info(f"Wrote {tb_path}")
                    updated_obj['thumbnail_path'] = tb_path
                else:
                    logger.trace(f"Cannot make thumbnail for {path} without aux image")

            if updated_obj:
                if not metadata:
                    # Metadata doesn't exist, create it
                    inserted = db.add_image_metadata([{
                        'collection': collection_name,
                        'path': dbimage.path,
                        **updated_obj
                    }])
                    if inserted==1:
                        logger.info(f"Inserted metadata for {dbimage.path}")
                    else:
                        logger.error(f"Error inserting metadata for {dbimage.path}")
                else:
                    # Metadata exists, update it
                    db.update_image_metadata(metadata.id, updated_obj)
                    logger.info(f"Updated metadata for {dbimage.path}")
        
        # Update the images with the new metadata ids if ncessary
        # This happens if we don't have user provided metadata and the metadatas
        # were created at the thumbnail generation step.
        path_to_metadata_id = db.get_path_to_metadata_id_map(collection_name)
        images = db.get_dbimages(collection=collection_name, page_size=0)['images']
        for dbimage in images:
            if dbimage.image_metadata_id is None:
                if dbimage.path in path_to_metadata_id:
                    dbimage.image_metadata_id = path_to_metadata_id[dbimage.path]
                    db.update_image(dbimage)
                    logger.info(f"Updated image {dbimage.path} with metadata id {dbimage.image_metadata_id}")
                else:
                    logger.warning(f"No metadata found for {dbimage.path}")

    logger.info("Database initialization complete.")
