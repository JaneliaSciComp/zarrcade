import json
from dataclasses import asdict
from typing import Iterator, Dict
from collections import defaultdict 

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text, MetaData, Table, Column, \
    String, Integer, Index, ForeignKey, func, select, distinct

from zarrcade.model import Image, MetadataImage
from zarrcade.settings import get_settings

if get_settings().debug_sql:
    import logging
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

IMAGES_AND_METADATA_SQL = text("""
    SELECT m.*, i.image_path, i.image_info
    FROM 
        images i
    LEFT JOIN 
        metadata m
    ON 
        m.id = i.metadata_id
""")

LIMIT_AND_OFFSET = text("""
    LIMIT :limit OFFSET :offset
""")

def deserialize_image_info(image_info: str) -> Image:
    """ Deserialize the Image from a JSON string.
    """
    return Image(**json.loads(image_info))

def serialize_image_info(image: Image) -> str:
    """ Serialize the Image into a JSON string.
    """
    return json.dumps(asdict(image))


class Database:
    """ Database which contains cached information about discovered images,
        as well as optional metadata for supporting searchability.
    """

    def __init__(self, db_url: str):

        # Initialize database
        self.engine = create_engine(db_url)
        self.meta = MetaData()
        self.meta.reflect(bind=self.engine)
        self.metadata_table, self.images_table = self.create_tables()

        # Read the attribute naming map from the database, if they exist
        self.column_map = {}
        self.reverse_column_map = {}
        if 'metadata_columns' in self.meta.tables:
            query = "SELECT * FROM metadata_columns"
            result_df = pd.read_sql_query(query, con=self.engine)
            for row in result_df.itertuples():
                db_name = row.db_name
                original_name = row.original_name
                logger.trace(f"Registering column '{db_name}' for {original_name}")
                self.column_map[db_name] = original_name
                self.reverse_column_map[original_name] = db_name


    def create_tables(self):
        """ Create tables if necessary and return the metadata and images tables 
            as a tuple.
        """
        if 'metadata' in self.meta.tables:
            metadata_table = self.meta.tables['metadata']
        else:
            logger.info("Creating empty metadata table")
            metadata_table = Table('metadata', self.meta,
                *self.get_metadata_columns(),
                extend_existing=True
            )
            metadata_table.create(self.engine)

        if 'images' in self.meta.tables:
            images_table = self.meta.tables['images']
        else:
            logger.info("Creating empty images table")
            images_table = Table('images', self.meta,
                Column('id', Integer, primary_key=True),
                Column('collection', String, nullable=False),
                Column('zarr_path', String, nullable=False),
                Column('group_path', String, nullable=False),
                Column('image_path', String, nullable=False, index=True),
                Column('image_info', String, nullable=False),
                Column('metadata_id', Integer,
                    ForeignKey('metadata.id', ondelete='SET NULL'),
                    nullable=True, index=True),
                Index('collection_zarr_path_idx', 'collection', 'zarr_path'),
                extend_existing=True)
            images_table.create(self.engine)

        return metadata_table, images_table


    def get_metadata_columns(self):
        """ Returns the static columns which are always present 
            in the metadata table.
        """
        return [
            Column('id', Integer, primary_key=True),  # Autoincrements by default in many DBMS
            Column('collection', String, nullable=False),
            Column('zarr_path', String, nullable=False),
            Column('aux_image_path', String, nullable=True),
            Column('thumbnail_path', String, nullable=True),
        ]

    def get_tuple_metadata(self, row):
        """ Get the image metadata out of a row and return it as a dictionary.
        """
        metadata = {}
        for k, v in self.column_map.items():
            if k in row._fields:
                metadata[v] = getattr(row, k)
        return metadata


    def get_images_count(self):
        """ Get the total number of images in the database.
        """
        with self.engine.begin() as conn:
            # pylint: disable-next=not-callable
            query = select(func.count()) \
                .select_from(self.images_table) \
                .where(self.images_table.c.image_info.isnot(None))
            result = conn.execute(query)
            return result.scalar()


    def get_zarr_path_to_metadata_id_map(self, collection: str):
        """ Build and return a dictionary which maps relative paths to 
            metadata ids. 
        """
        metadata_ids = {}
        query = "SELECT id,zarr_path FROM metadata WHERE collection = :collection"
        result_df = pd.read_sql_query(query, con=self.engine, params={'collection': collection})
        for row in result_df.itertuples():
            metadata_ids[row.zarr_path] = row.id
        return metadata_ids


    def persist_images(
            self,
            collection: str,
            image_generator: Iterator[Image],
            only_with_metadata: bool = False
        ):
        """ Discover images in the filestore 
            and persist them in the given database.
        """
        # Temporarily cache zarr_path -> metadata id lookup table
        metadata_ids = self.get_zarr_path_to_metadata_id_map(collection)
        logger.info(f"Loaded {len(metadata_ids)} metadata ids")
        # Walk the storage root and populate the database
        count = 0

        for image in image_generator():
            relative_path = image.zarr_path
            if relative_path in metadata_ids:
                metadata_id = metadata_ids[relative_path]
            else:
                metadata_id = None

            if metadata_id or not only_with_metadata:
                logger.debug(f"Persisting {image}")
                self.persist_image(
                            collection=collection,
                            image=image,
                            metadata_id=metadata_id
                )
                count += 1
            else:
                logger.debug(f"Skipping image missing metadata: {image.zarr_path}")

        logger.info(f"Persisted {count} images to the database")


    def persist_image(self, collection: str, image: Image, metadata_id: int):
        """ Persist (update or insert) the given image.
        """
        image_path = image.relative_path
        zarr_path = image.zarr_path
        group_path = image.group_path
        image_info = serialize_image_info(image)

        with self.engine.begin() as conn:
            stmt = select(self.images_table).\
                where((self.images_table.c.collection == collection) & 
                    (self.images_table.c.image_path == image_path))
            existing_row = conn.execute(stmt).fetchone()

            if existing_row:
                update_stmt = self.images_table.update(). \
                    where((self.images_table.c.collection == collection) &
                            (self.images_table.c.image_path == image_path)). \
                    values(zarr_path=zarr_path,
                            group_path=group_path,
                            image_info=image_info,
                            metadata_id=metadata_id)
                conn.execute(update_stmt)
                logger.info(f"Updated {image_path}")
            else:
                insert_stmt = self.images_table.insert() \
                        .values(collection=collection,
                                zarr_path=zarr_path,
                                group_path=group_path,
                                image_path=image_path,
                                image_info=image_info,
                                metadata_id=metadata_id)
                conn.execute(insert_stmt)
                logger.info(f"Inserted {image_path}")


    def get_metaimage(self, image_path: str):
        """ Returns the MetadataImage for the given image path, or 
            None if it doesn't exist.
        """
        full_query = text(f"{IMAGES_AND_METADATA_SQL} WHERE i.image_path = :image_path")
        result_df = pd.read_sql_query(full_query, con=self.engine, params={'image_path': image_path})
        for row in result_df.itertuples():
            zarr_path = row.zarr_path
            image_info_json = row.image_info
            logger.info(f"Found {row.image_path} in image collection")
            if image_info_json:
                image = deserialize_image_info(image_info_json)
                metadata = self.get_tuple_metadata(row)
                metaimage = MetadataImage(
                    id=zarr_path,
                    image=image,
                    aux_image_path=row.aux_image_path,
                    thumbnail_path=row.thumbnail_path,
                    metadata=metadata)
                return metaimage
            else:
                logger.info(f"Image has no image_info: {image_path}")
                return None
     
        logger.info(f"Image not found: {image_path}")
        return None


    def find_metaimages(self,
            search_string: str = '',
            filter_params: Dict[str,str] = None,
            page: int = 0,
            page_size: int = 0
        ):
        """
        Find meta images with optional search and pagination.

        Args:
            search_string (str): The string to search for within image metadata.
            page (int): The one-indexed page number.
            page_size (int): The number of results per page. 0 means infinite.

        Returns:
            tuple: A tuple containing:
                - List of `MetadataImage` objects.
                - Total number of pages.
        """
        if page < 0:
            raise ValueError("Page index must be a non-negative integer.")

        offset = (page - 1) * page_size

        # Base queries for fetching data and counting total records
        base_query = IMAGES_AND_METADATA_SQL
        where_clause = ''
        params = {}

        if search_string:
            search_columns = [f"m.{k}" for k in self.column_map] + ['i.zarr_path']
            or_clauses = " OR ".join([f"{col} LIKE :search_string" for col in search_columns])
            where_clause += f" AND ({or_clauses})"
            params['search_string'] = f'%{search_string}%'

        for db_name in filter_params:
            where_clause += f" AND (m.{db_name} LIKE :{db_name}_value)"
            params[f"{db_name}_value"] = f'%{filter_params[db_name]}%'

        paginated_query = f"{base_query} WHERE 1=1{where_clause}"
        count_query = f"SELECT COUNT(*) FROM ({base_query} WHERE 1=1{where_clause})"

        paged_params = params
        if page_size>0:
            paged_params = params | {
                'limit': page_size,
                'offset': offset
            }
            paginated_query += " LIMIT :limit OFFSET :offset"

        result_df = pd.read_sql_query(text(paginated_query), con=self.engine, params=paged_params)
        total_count = pd.read_sql_query(text(count_query), con=self.engine, params=params).iloc[0, 0]

        # Calculate the total number of pages
        total_pages = (total_count + page_size - 1) // page_size

        images = []
        for row in result_df.itertuples():
            metadata = self.get_tuple_metadata(row)
            image_info_json = row.image_info
            image_path = row.image_path
            if image_info_json:
                image = deserialize_image_info(image_info_json)
                metaimage = MetadataImage(
                    id=image_path,
                    image=image,
                    aux_image_path=row.aux_image_path,
                    thumbnail_path=row.thumbnail_path,
                    metadata=metadata
                )
                logger.trace(f"matched {metaimage.id}")
                images.append(metaimage)

        start_num = ((page-1) * page_size) + 1
        end_num = start_num + page_size - 1
        if end_num > total_count: 
            end_num = total_count

        return {
            'images': images,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'total_count': total_count,
                'start_num': start_num,
                'end_num': end_num
            }
        }


    def get_unique_values(self, column_name):
        """ Return a map of unique values to their counts 
            from the given column.
        """
        query = text((f"SELECT m.{column_name}, COUNT(*) "
                      f"FROM ({IMAGES_AND_METADATA_SQL}) m "
                      f"GROUP BY m.{column_name}"))

        with self.engine.connect() as connection:
            result = connection.execute(query)
            value_counts = {row[0]: row[1] for row in result.fetchall()}
            if None in value_counts:
                logger.debug(f"Ignoring {value_counts[None]} items with no value for {column_name}")
                del value_counts[None]
            return value_counts


    def get_unique_comma_delimited_values(self, column_name):
        """ Return a map of unique values to their counts
            from a column whose values are comma delimited lists. 
        """
        query = text((f"SELECT m.{column_name} "
                      f"FROM ({IMAGES_AND_METADATA_SQL}) m"))

        with self.engine.connect() as connection:
            result = connection.execute(query)
            value_counts = defaultdict(int)
            for row in result.fetchall():
                value = row[0]
                if value:
                    for item in value.split(','):
                        item = item.strip()
                        value_counts[item] += 1

        return dict(value_counts)