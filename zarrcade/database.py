import json
from dataclasses import asdict
from typing import Iterator

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text, MetaData, Table, Column, \
    String, Integer, Index, ForeignKey, func, select

from zarrcade.model import Image, MetadataImage

# Uncomment for debugging purposes
# import logging
# logging.basicConfig()
# logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


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

def deserialize_image_info(image_info: str):
    return Image(**json.loads(image_info))

def serialize_image_info(image: Image):
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

        # Read the attribute naming map from the database, if they exist
        self.attr_map = {}
        if 'metadata_columns' in self.meta.tables:
            query = "SELECT * FROM metadata_columns"
            result_df = pd.read_sql_query(query, con=self.engine)
            for row in result_df.itertuples():
                db_name = row.db_name
                original_name = row.original_name
                logger.trace(f"Registering column '{db_name}' for {original_name}")
                self.attr_map[db_name] = original_name

        self.metadata_table, self.images_table = self.create_tables()


    def create_tables(self):
        # Create empty metadata table if necessary
        if 'metadata' in self.meta.tables:
            metadata_table = self.meta.tables['metadata']
        else:
            logger.info("Creating empty metadata table")
            metadata_table = Table('metadata', self.meta,
                *self.get_metadata_columns(),
                extend_existing=True
            )
            metadata_table.create(self.engine)

        # Create empty images table if necessary
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
                Index('collection_relpath_idx', 'collection', 'zarr_path'),
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
            Column('relpath', String, nullable=False),
            Column('aux_image_path', String, nullable=True),
            Column('thumbnail_path', String, nullable=True),
        ]

    def get_tuple_metadata(self, row):
        """ Get the image metadata out of a row and return it as a dictionary.
        """
        metadata = {}
        for k, v in self.attr_map.items():
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


    def get_relpath_to_metadata_id_map(self, collection: str):
        """ Build and return a dictionary which maps relative paths to 
            metadata ids. 
        """
        metadata_ids = {}
        query = "SELECT id,relpath FROM metadata WHERE collection = :collection"
        result_df = pd.read_sql_query(query, con=self.engine, params={'collection': collection})
        for row in result_df.itertuples():
            metadata_ids[row.relpath] = row.id
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
        # Temporarily cache relpath -> metadata id lookup table
        metadata_ids = self.get_relpath_to_metadata_id_map(collection)
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
            relpath = row.relpath
            image_info_json = row.image_info
            logger.info(f"Found {row.image_path} in image collection")
            if image_info_json:
                image = deserialize_image_info(image_info_json)
                metadata = self.get_tuple_metadata(row)
                metaimage = MetadataImage(
                    id=relpath,
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


    def find_metaimages(self, search_string: str = '', page: int = 1, page_size: int = 10):
        """
        Find meta images with optional search and pagination.

        Args:
            search_string (str): The string to search for within image metadata.
            page (int): The one-indexed page number.
            page_size (int): The number of results per page.

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

        # Modify queries based on whether a search string is provided
        if not search_string:
            paginated_query = text(f"{base_query} LIMIT :limit OFFSET :offset")
            count_query = text(f"SELECT COUNT(*) FROM ({base_query})")
            result_df = pd.read_sql_query(paginated_query, con=self.engine, params={'limit': page_size, 'offset': offset})
            total_count = pd.read_sql_query(count_query, con=self.engine).iloc[0, 0]
        else:
            cols = [f"m.{k}" for k in self.attr_map] + ['i.relpath']
            query_string = " OR ".join([f"{col} LIKE :search_string" for col in cols])
            paginated_query = text(f"{base_query} WHERE {query_string} LIMIT :limit OFFSET :offset")
            count_query = text(f"SELECT COUNT(*) FROM ({base_query} WHERE {query_string})")
            
            result_df = pd.read_sql_query(paginated_query, con=self.engine, params={
                'search_string': f'%{search_string}%',
                'limit': page_size,
                'offset': offset
            })
            total_count = pd.read_sql_query(count_query, con=self.engine, params={
                'search_string': f'%{search_string}%'
            }).iloc[0, 0]

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
                logger.debug(f"  adding {metaimage.id}")
                images.append(metaimage)

        return {
            'images': images,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'total_count': total_count
            }
        }