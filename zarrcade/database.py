import json
from dataclasses import asdict
from typing import Iterator, Dict
from collections import defaultdict

import pandas as pd
from loguru import logger
from sqlalchemy import create_engine, text, func
from sqlalchemy import String, Integer, Index, ForeignKey, MetaData, Table, Column, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError

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


class Base(DeclarativeBase):
    pass

class DBCollection(Base):
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    data_url = Column(String, nullable=False)


class DBMetadataColumn(Base):
    __tablename__ = 'metadata_columns'
    id = Column(Integer, primary_key=True, autoincrement=True)
    db_name = Column(String, nullable=False, unique=True)
    original_name = Column(String, nullable=False)
    

class DBImageMetadata(Base):
    __tablename__ = 'image_metadata'
    id = Column(Integer, primary_key=True)
    collection = Column(String, nullable=False)
    path = Column(String, nullable=False)
    aux_image_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    images = relationship('DBImage', back_populates='image_metadata', uselist=True)

    __table_args__ = (
        UniqueConstraint('collection', 'path', name='uq_collection_path'),
        Index('ix_collection_path', 'collection', 'path')
    )

class DBImage(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    collection = Column(String, nullable=False)
    image_path = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False)
    group_path = Column(String, nullable=False)
    image_info = Column(String, nullable=False)
    image_metadata_id = Column(Integer, ForeignKey('image_metadata.id'), nullable=True, index=True)
    image_metadata = relationship('DBImageMetadata', back_populates='images')
    
    __table_args__ = (
        Index('collection_path_idx', 'collection', 'path'),
    )

class Database:
    """ Database which contains cached information about discovered images,
        as well as optional metadata for supporting searchability.
    """

    def __init__(self, db_url: str):

        # Initialize database
        self.engine = create_engine(db_url)

        # Create tables if necessary
        Base.metadata.create_all(self.engine)

        # Create a session maker
        self.sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        self.load()


    def load(self):

        # Reflect current schema
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

        # Read the collections from the database
        with self.sessionmaker() as session:
            result = session.query(DBCollection).all()
            self.collection_map = {item.name: item.data_url for item in result}
            self.reverse_collection_map = {item.data_url: item.name for item in result}

        # Read the attribute naming map from the database
        with self.sessionmaker() as session:
            result = session.query(DBMetadataColumn).all()
            self.column_map = {item.db_name: item.original_name for item in result}
            self.reverse_column_map = {item.original_name: item.db_name for item in result}


    def get_table(self, table_name):
        return Table(table_name, self.metadata, autoload_with=self.engine)


    def add_collection(self, name, data_url):

        if name in self.collection_map:
            # Collection already exists
            return

        with self.engine.connect() as connection:
            # Insert into collections
            collections = self.get_table('collections')
            insert_stmt = collections.insert().values(name=name, data_url=data_url)
            connection.execute(insert_stmt)
            connection.commit()

            # Update internal state
            self.collection_map[name] = data_url
            self.reverse_collection_map[data_url] = name
            print(f"Added new collection: {name} (url={data_url})")


    def add_metadata_column(self, db_name, original_name):

        if db_name in self.column_map:
            # Column already exists
            return

        with self.engine.connect() as connection:
            try:
                # Add column to the image_metadata table
                alter_stmt = text(f'ALTER TABLE image_metadata ADD COLUMN {db_name} VARCHAR')
                connection.execute(alter_stmt)

                # Reload the table definitions and cached data
                self.load()

            except OperationalError as e:
                # This can happen if the image_metadata table gets out of sync
                # with the metadata_columns
                logger.warning(f'Cannot alter table: {e}')

            # Insert into metadata_columns
            metadata_columns = self.get_table('metadata_columns')
            insert_stmt = metadata_columns.insert().values(db_name=db_name, original_name=original_name)
            connection.execute(insert_stmt)
            connection.commit()

            # Update internal state
            self.column_map[db_name] = original_name
            self.reverse_column_map[original_name] = db_name
            print(f"Added new metadata column: {db_name} (original={original_name})")


    def add_image_metadata(self, image_metadata_rows):

        metadata_table = self.get_table('image_metadata')
        with self.sessionmaker() as session:
            try:
                inserted = 0
                for row in image_metadata_rows:
                    new_metadata = metadata_table.insert().values(row)
                    try:
                        session.execute(new_metadata)
                        inserted += 1
                    except IntegrityError:
                        pass

                session.commit()
                return inserted

            except OperationalError as e:
                print(f"Error inserting data: {e}")
                session.rollback()


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
        with self.sessionmaker() as session:
            # pylint: disable=not-callable
            count = session.query(func.count(DBImage.id)) \
                           .filter(DBImage.image_info.isnot(None)).scalar()
            return count


    def get_path_to_metadata_id_map(self, collection: str):
        """ Build and return a dictionary which maps relative paths to 
            metadata ids. 
        """
        with self.sessionmaker() as session:
            query = session.query(DBImageMetadata.path, DBImageMetadata.id) \
                        .filter(DBImageMetadata.collection == collection)
            path_to_id = {path: _id for path, _id in query}
            return path_to_id


    def persist_images(
            self,
            collection: str,
            image_generator: Iterator[Image],
            only_with_metadata: bool = False
        ):
        """ Discover images in the filestore 
            and persist them in the given database.
        """
        # Metadata id lookup table
        metadata_ids = self.get_path_to_metadata_id_map(collection)
        logger.info(f"Loaded {len(metadata_ids)} metadata ids for collection '{collection}'")

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
        path = image.zarr_path
        group_path = image.group_path
        image_info = serialize_image_info(image)

        new_values = dict(
            path=path,
            group_path=group_path,
            image_info=image_info,
            image_metadata_id=metadata_id
        )

        with self.sessionmaker() as session:
            try:
                image = session.query(DBImage).filter_by(collection=collection, image_path=image_path).first()
                if image:
                    # Update existing record with new values
                    for key, value in new_values.items():
                        setattr(image, key, value)
                    session.commit()
                else:
                    # Insert new record
                    new_image = DBImage(collection=collection, image_path=image_path, **new_values)
                    session.add(new_image)
                    session.commit()

            except SQLAlchemyError as e:
                session.rollback()
                print(f"An error occurred: {e}")


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
                    collection=row.collection,
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
                    collection=row.collection,
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