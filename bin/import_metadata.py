#!/usr/bin/env python3 

import re
import unicodedata
import argparse
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table

parser = argparse.ArgumentParser(
    description='Create an ngffbrowse database by importing metadata from a CSV file')
parser.add_argument('-i', '--input_path', type=str, required=True, 
    help='Path to the CSV file containing the metadata')
parser.add_argument('-r', '--root_url', type=str, required=True, 
    help='Path to the root directory containing the images')
parser.add_argument('-d', '--db_url', type=str, default="sqlite:///database.db", 
    help='URL for the output database')
parser.add_argument('--overwrite', action=argparse.BooleanOptionalAction, default=False,
    help="Overwrite tables if they exist?")

args = parser.parse_args()
csv_file_path = args.input_path
fs_root = args.root_url
db_url = args.db_url
overwrite = args.overwrite

# Read the CSV
df = pd.read_csv(csv_file_path)
path_column_name = df.columns[0]
print(f"Parsed {df.shape[0]} rows from input CSV")
print(f"The first column '{path_column_name}' will be treated as the relative path to the images")

# Connect to the database
engine = create_engine(db_url)
meta = MetaData()
meta.reflect(bind=engine)

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
# Skip the first column which is the relpath
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
print("Metadata columns:")
print(df_cols)

# Save the column map to the database
if overwrite or 'metadata_columns' not in meta.tables:
    
    if 'metadata_columns' in meta.tables: 
        print(f"Dropping existing metadata_columns table")
        meta.tables.get('metadata_columns').drop(engine)

    df_cols.to_sql('metadata_columns', con=engine, if_exists='replace', index=False)
    print(f"Imported {df_cols.shape[0]} columns into metadata_columns table")

elif not overwrite:
    print("metadata_columns table already exists. Pass --overwrite if you want to recreate it.")

# Save metadata to the database
if overwrite or 'metadata' not in meta.tables:

    # Process metadata into table format
    rename_logic = lambda x, idx: x if idx == 0 else col2slug[x]
    df.columns = [rename_logic(x, i) for i, x in enumerate(df.columns)]
    df.rename(columns={path_column_name: 'relpath'}, inplace=True)
    df.insert(0, 'collection', fs_root)

    table_columns = [
        Column('id', Integer, primary_key=True),  # Autoincrements by default in many DBMS
        Column('collection', String, nullable=False),
        Column('relpath', String, nullable=False)
    ]
    for colname in col2slug.keys():
        table_columns.append(Column(colname, String))
    
    if 'metadata' in meta.tables: 
        print(f"Dropping existing metadata table")
        meta.tables.get('metadata').drop(engine)

    # Create table
    metadata_table = Table('metadata', meta, *table_columns, extend_existing=True)
    meta.create_all(engine)
    print(f"Created metadata table")

    # Load data
    df.to_sql(metadata_table.name, con=engine, if_exists='replace', index=False)
    print(f"Imported {df.shape[0]} images into metadata table")

elif not overwrite:
    print("metadata table already exists. Pass --overwrite if you want to recreate it.")
