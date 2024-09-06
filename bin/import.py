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
from sqlalchemy import Column, String, Table

from zarrcade import Database, Filestore
from zarrcade.settings import get_settings

SKIP_FILE_CHECKS = True

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
    parser.add_argument('-m', '--metadata-path', type=str,
        help='Path to the CSV file containing additional metadata')
    parser.add_argument('-a', '--aux-path', type=str, default=".zarrcade",
        help='Path to the folder containing auxiliary images, relative to the root_url.')
    parser.add_argument('--aux-image-name', type=str, default='zmax_bc.png',
        help='Filename of the main auxiliary image.')
    parser.add_argument('--thumbnail-name', type=str, default='zmax_300.jpg',
        help='Filename of the thumbnail image for the gallery view.')
    parser.add_argument('--only-with-metadata', action=argparse.BooleanOptionalAction, default=False,
        help="Only load images for which metadata is provided?")

    args = parser.parse_args()
    data_url = args.data_url
    collection = slugify(args.collection_name)
    metadata_path = args.metadata_path

    # Connect to the filestore
    logger.info(f"Data URL is {data_url}")
    fs = Filestore(data_url)

    # Connect to the database
    settings = get_settings()
    db_url = str(settings.db_url)
    logger.info(f"Database URL is {db_url}")
    db = Database(db_url)
    engine = db.engine
    meta = db.metadata

    logger.info("Current collections:")
    for key, value in db.collection_map.items():
        logger.info(f"  {key}: {value}")

    logger.info("Current metadata columns:")
    for key, value in db.column_map.items():
        logger.info(f"  {key}: {value}")

    # Set up the collection
    db.add_collection(collection, data_url)

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
                
        def get_aux_path(filename, zarr_path):
            zarr_name, _ = os.path.splitext(zarr_path)
            aux_path = os.path.join(args.aux_path, zarr_name, filename)
            if SKIP_FILE_CHECKS:
                return aux_path
            elif fs.exists(aux_path):
                logger.trace(f"Found auxiliary file: {fs.fsroot}/{aux_path}")
                return aux_path
            else:
                logger.trace(f"Missing auxiliary file: {fs.fsroot}/{aux_path}")
                return None
                
        new_objs = []
        for _, row in df.iterrows():
            path = row[path_column_name]
            new_obj = {db.reverse_column_map[c]: row[c] for c in columns}
            new_obj['collection'] = collection
            new_obj['path'] = path

            if args.aux_image_name:
                new_obj['aux_image_path'] = get_aux_path(args.aux_image_name, path)

            if args.thumbnail_name:
                new_obj['thumbnail_path'] = get_aux_path(args.thumbnail_name, path)

            new_objs.append(new_obj)

        inserted = db.add_image_metadata(new_objs)

    # Load the images
    db.persist_images(collection, fs.yield_images,
        only_with_metadata=args.only_with_metadata)

    logger.info("Database initialization complete.")
