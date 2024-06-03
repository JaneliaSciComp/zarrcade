#!/usr/bin/env python3
"""
Initialize a Zarrcade database by walking a filesystem and discovering Zarrs. 
Optionally uses an auxilary image store for finding 2d thumbnails.
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

parser = argparse.ArgumentParser(
    description=__doc__,
    formatter_class=argparse.ArgumentDefaultsHelpFormatter
)

parser.add_argument('-m', '--metadata-path', type=str, required=True,
    help='Path to the CSV file containing additional metadata')
parser.add_argument('-a', '--aux-path', type=str, default=".zarrcade",
    help='Path to the folder containing auxiliary images, relative to the root_url.')
parser.add_argument('--aux-image-name', type=str, default='zmax.png',
    help='Filename of the main auxiliary image.')
parser.add_argument('--thumbnail-name', type=str, default='zmax_300.jpg',
    help='Filename of the thumbnail image.')
parser.add_argument('--overwrite', action=argparse.BooleanOptionalAction, default=False,
    help="Overwrite tables if they exist?")
parser.add_argument('--only-with-metadata', action=argparse.BooleanOptionalAction, default=False,
    help="Only load images with provided metadata?")

args = parser.parse_args()
metadata_path = args.metadata_path
overwrite = args.overwrite

# Read settings from environment or YAML
settings = get_settings()
data_url = str(settings.data_url)
db_url = str(settings.db_url)

# Connect to the filestore
logger.info(f"Data URL is {data_url}")
fs = Filestore(data_url)

# Connect to the database
logger.info(f"Database URL is {db_url}")
db = Database(db_url)
engine = db.engine
meta = db.meta

# Read the metadata
logger.info(f"Reading {metadata_path}")
df = pd.read_csv(metadata_path)
path_column_name = df.columns[0]
logger.info(f"Parsed {df.shape[0]} rows from metadata CSV")
logger.info(f"The first column '{path_column_name}' will be treated as the relative path")

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
    return 'c_'+re.sub(r"[-\s]+", "_", value).strip("-_")

col2slug = {}
db_names = []
original_names = []
# Skip the first column which is the zarr_path
columns = df.columns[1:]
# Slugify the column names
for original_name in columns:
    db_name = slugify(original_name)
    db_names.append(db_name)
    original_names.append(original_name)
    col2slug[original_name] = db_name

df_cols = pd.DataFrame(data={
    'db_name': db_names,
    'original_name': original_names
})
logger.info("Metadata columns:")
print(df_cols)

# Save the column map to the database
if overwrite or 'metadata_columns' not in meta.tables:

    if 'metadata_columns' in meta.tables:
        logger.info("Dropping existing metadata_columns table")
        meta.tables.get('metadata_columns').drop(engine)

    df_cols.to_sql('metadata_columns', con=engine, if_exists='replace', index=False)
    logger.info(f"Imported {df_cols.shape[0]} columns into metadata_columns table")

elif not overwrite:
    logger.info("metadata_columns table already exists. Pass --overwrite if you want to recreate it.")

# Save metadata to the database
if overwrite or 'metadata' not in meta.tables:

    # Process metadata into table format
    def rename_logic(x, idx):
        return x if idx == 0 else col2slug[x]
    df.columns = [rename_logic(x, i) for i, x in enumerate(df.columns)]
    df.rename(columns={path_column_name: 'zarr_path'}, inplace=True)
    df.insert(0, 'collection', fs.fsroot)

    if 'metadata' in meta.tables:
        logger.info("Dropping existing metadata table")
        meta.tables.get('metadata').drop(engine)
        meta.remove(Table('metadata', meta))

    # Create metadata table
    logger.info('Creating metadata table')
    table_columns = db.get_metadata_columns()
    for colname in col2slug.values():
        table_columns.append(Column(colname, String))
        
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

    if args.aux_image_name:
        df['aux_image_path'] = df['zarr_path'].apply(partial(get_aux_path, args.aux_image_name))

    if args.thumbnail_name:
        df['thumbnail_path'] = df['zarr_path'].apply(partial(get_aux_path, args.thumbnail_name))

    metadata_table = Table('metadata', meta, *table_columns, extend_existing=True)
    meta.create_all(engine)
    logger.info(f"Created empty metadata table with {len(table_columns)} user-defined columns")

    # Load data
    df.to_sql(metadata_table.name, con=engine, if_exists='append', index=False)
    logger.info(f"Imported {df.shape[0]} images into metadata table")

elif not overwrite:
    logger.info("Metadata table already exists. Pass --overwrite if you want to recreate it.")

# Now load the images
if overwrite or 'images' not in meta.tables:

    if 'images' in meta.tables:
        logger.info("Dropping existing images table")
        meta.tables.get('images').drop(engine)
        meta.remove(Table('images', meta))

    db.create_tables()
    db.persist_images(fs.fsroot, fs.yield_images,
        only_with_metadata=args.only_with_metadata)

elif not overwrite:
    logger.info("Images table already exists. Pass --overwrite if you want to recreate it.")

logger.info("Database initialization complete.")
