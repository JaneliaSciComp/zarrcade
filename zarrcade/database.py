""" Data model and API for accessing the data
"""
import json
from dataclasses import asdict
from typing import Iterator, Dict, List
from collections import defaultdict

from loguru import logger
from sqlalchemy import create_engine, text, func, and_, or_
from sqlalchemy import String, Integer, Index, ForeignKey, MetaData, Table, Column, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker, contains_eager
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError

from zarrcade.model import Image
from zarrcade.settings import get_settings


if get_settings().database.debug_sql:
    import logging
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

class Base(DeclarativeBase):
    pass

class DBCollection(Base):
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    settings_path = Column(String, nullable=True)


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

    def get_image(self) -> Image:
        """ Deserialize the Image from a JSON string.
        """
        return Image(**json.loads(self.image_info))

    def set_image(self, image: Image) -> str:
        """ Serialize the Image into a JSON string.
        """
        self.image_info = json.dumps(asdict(image))


class Database:
    """ Database which contains cached information about discovered images,
        as well as optional metadata for supporting searchability.
    """

    def __init__(self, db_url: str):    
        """ Initialize the database.

            Args:
                db_url (str): The URL of the database.
        """
        logger.trace(f"Initializing database at {db_url}")

        # Initialize database
        self.engine = create_engine(db_url)

        # Create tables if necessary
        Base.metadata.create_all(self.engine)

        # Create a session maker
        self.sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Load the current state of the database
        self.load()


    def load(self):
        """ Load the current state of the database.
        """

        # Reflect current schema
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)

        # Read the collections from the database
        with self.sessionmaker() as session:
            result = session.query(DBCollection).all()
            self.collection_map = {item.name: item for item in result}
            self.reverse_collection_map = {item.data_url: item for item in result}

        # Read the attribute naming map from the database
        with self.sessionmaker() as session:
            result = session.query(DBMetadataColumn).all()
            self.column_map = {item.db_name: item.original_name for item in result}
            self.reverse_column_map = {item.original_name: item.db_name for item in result}

        # Add dynamic metadata columns
        for column in self.column_map:
            if not hasattr(DBImageMetadata, column):
                setattr(DBImageMetadata, column, Column(column, String))


    def get_table(self, table_name: str) -> Table:
        """ Get a SQLAlchemy table from the database.

            Args:
                table_name (str): The name of the table.

            Returns:
                Table: The table loaded from the database.
        """
        return Table(table_name, self.metadata, autoload_with=self.engine)


    def add_collection(self, name, label, data_url):
        """ Add a new collection to the database.

            Args:
                name (str): The name of the collection.
                label (str): The human-readable label for the collection.
                data_url (str): The URL of the collection.
        """
        if name in self.collection_map:

            if self.collection_map[name].data_url != data_url:
                # Collection already exists, but with a different URL
                raise ValueError(f"Collection {name} already exists with a different URL: {self.collection_map[name].data_url}")
                
            # Update the label if it has changed
            if self.collection_map[name].label != label:
                with self.engine.connect() as connection:
                    collections = self.get_table('collections')
                    update_stmt = collections.update().where(collections.c.name == name).values(label=label)
                    connection.execute(update_stmt)
                    connection.commit()
                    self.collection_map[name].label = label
                    logger.info(f"Updated label for collection {name} to {label}")

            # Collection already exists
            return

        if label is None:
            label = name
        with self.engine.connect() as connection:
            # Insert into collections
            collections = self.get_table('collections')
            insert_stmt = collections.insert().values(name=name, label=label, data_url=data_url)
            connection.execute(insert_stmt)
            connection.commit()

            # Fetch the inserted collection
            select_stmt = collections.select().where(collections.c.name == name)
            result = connection.execute(select_stmt).fetchone()

            # Update internal state
            self.collection_map[name] = result
            self.reverse_collection_map[data_url] = result
            logger.info(f"Added new collection: {name} (label={label}, url={data_url})")


    def add_metadata_column(self, db_name, original_name):
        """ Add a new dynamic metadata column to the database.

            Args:
                db_name (str): The name of the new column in the database.
                original_name (str): The original name (i.e. label) of the column.
        """
        if db_name in self.column_map:
            # Column already exists
            logger.debug(f"Column {db_name} already exists")
            return

        with self.engine.connect() as connection:
            try:
                # Add column to the image_metadata table
                alter_stmt = text(f'ALTER TABLE image_metadata ADD COLUMN {db_name} VARCHAR')
                connection.execute(alter_stmt)

            except OperationalError as e:
                # This can happen if the image_metadata table gets out of sync
                # with the metadata_columns
                logger.warning(f'Cannot alter table: {e}')

            # Insert into metadata_columns
            metadata_columns = self.get_table('metadata_columns')
            insert_stmt = metadata_columns.insert().values(
                db_name=db_name, 
                original_name=original_name
            )
            connection.execute(insert_stmt)
            connection.commit()

            # Update internal state
            self.column_map[db_name] = original_name
            self.reverse_column_map[original_name] = db_name
            self.load()
            logger.info(f"Added new metadata column: {db_name} (original={original_name})")
            

    def add_image_metadata(self, image_metadata_rows: List[Dict[str,str]]) -> int:
        """ Add metadata for a set of images.

            Args:
                image_metadata_rows (list): A list of dictionaries, 
                    where each dictionary represents a row of metadata 
                    for an image.
        """
        metadata_table = self.get_table('image_metadata')
        with self.sessionmaker() as session:
            try:
                inserted = 0
                updated = 0
                for row in image_metadata_rows:
                    new_metadata = metadata_table.insert().values(row)
                    try:
                        session.execute(new_metadata)
                        inserted += 1
                    except IntegrityError:
                        # Try updating instead
                        update_stmt = metadata_table.update().where(
                            and_(
                                metadata_table.c.collection == row['collection'],
                                metadata_table.c.path == row['path']
                            )
                        ).values(row)
                        result = session.execute(update_stmt)
                        if result.rowcount > 0:
                            updated += 1

                session.commit()

                if inserted+updated < len(image_metadata_rows):
                    logger.warning(f"Only added {inserted+updated} rows of {len(image_metadata_rows)}")

                return inserted, updated

            except OperationalError as e:
                session.rollback()
                logger.exception(f"Error inserting data: {e}")


    def update_image_metadata(self, metadata_id: int, updated_metadata: Dict[str, str]) -> bool:
        """ Update the metadata for an image.

            Args:
                metadata_id (int): The ID of the metadata to update.
                updated_metadata (dict): A dictionary containing the updated metadata.

            Returns:
                bool: True if the metadata was updated, False otherwise.
        """
        metadata_table = self.get_table('image_metadata')
        with self.sessionmaker() as session:
            try:
                update_stmt = metadata_table.update().where(
                    metadata_table.c.id == metadata_id
                ).values(updated_metadata)
                result = session.execute(update_stmt)
                session.commit()
                return result.rowcount > 0
            except OperationalError as e:
                session.rollback()
                logger.exception(f"Error updating metadata: {e}")
                return False


    def get_all_image_metadata(self) -> List[DBImageMetadata]:
        """ Get all image metadata from the database.
        """
        with self.sessionmaker() as session:
            return session.query(DBImageMetadata).all()


    def get_images_count(self) -> int:
        """ Get the total number of images in the database.

            Returns:
                int: The number of images in the database.
        """
        with self.sessionmaker() as session:
            # pylint: disable=not-callable
            count = session.query(func.count(DBImage.id)) \
                           .filter(DBImage.image_info.isnot(None)).scalar()
            return count


    def get_path_to_metadata_id_map(self, collection: str) -> Dict[str,int]:
        """ Build and return a dictionary which maps relative paths to 
            metadata ids. 

            Args:
                collection (str): The name of the collection.

            Returns:
                dict: A dictionary which maps relative paths to metadata ids.
        """
        with self.sessionmaker() as session:
            query = session.query(DBImageMetadata.path, DBImageMetadata.id) \
                        .filter(DBImageMetadata.collection == collection)
            path_to_id = {path: _id for path, _id in query}
            return path_to_id


    def persist_image(self, collection: str, path: str, image: Image, metadata_id: int) -> bool:
        """ Save (update or insert) the given image to the database.

            Args:
                collection (str): The name of the collection.
                image (Image): The image to persist.
                metadata_id (int): The metadata id for the image.

            Returns:
                bool: True if the image was inserted, False if it was updated.
        """
        logger.trace(f"Persisting image {image}")
        group_path = image.group_path
        image_path = f"{path}{group_path}"

        with self.sessionmaker() as session:
            try:
                db_image = session.query(DBImage) \
                                  .filter_by(collection=collection, image_path=image_path) \
                                  .first()
                if db_image:
                    # Update existing record with new values
                    db_image.path = path
                    db_image.group_path = group_path
                    db_image.image_metadata_id = metadata_id
                    db_image.set_image(image)
                    session.commit()
                    logger.info(f"Updated image {image_path}")
                    return False
                else:
                    # Insert new record
                    new_image = DBImage(
                        collection = collection,
                        image_path = image_path,
                        path = path,
                        group_path = group_path,
                        image_metadata_id = metadata_id
                    )
                    new_image.set_image(image)
                    session.add(new_image)
                    session.commit()
                    logger.info(f"Inserted image {image_path}")
                    return True

            except SQLAlchemyError as e:
                session.rollback()
                logger.exception(f"An error occurred: {e}")


    def persist_images(
            self,
            collection: str,
            image_generator: Iterator[Image],
            only_with_metadata: bool = False
        ) -> int:
        """ Save images from the provided generator to the given collection.

            Args:
                collection (str): The name of the collection.
                image_generator (Iterator[Image]): An iterator which returns images.
                only_with_metadata (bool): If True, only images with metadata will be persisted.
            
            Returns:
                int: The number of images persisted.
        """
        # Metadata id lookup table
        metadata_ids = self.get_path_to_metadata_id_map(collection)
        logger.info(f"Loaded {len(metadata_ids)} metadata ids for collection '{collection}'")

        # Walk the storage root and populate the database
        count = 0

        for path, image in image_generator():
            full_path = f"{path}{image.group_path}"

            if full_path in metadata_ids:
                metadata_id = metadata_ids[full_path]
            elif path in metadata_ids:
                metadata_id = metadata_ids[path]
            else:
                metadata_id = None

            if metadata_id or not only_with_metadata:
                self.persist_image(
                    collection=collection,
                    path=path,
                    image=image,
                    metadata_id=metadata_id
                )
                count += 1
            else:
                logger.debug(f"Skipping image missing metadata: {path}")

        logger.debug(f"Persisted {count} images to the database")
        return count


    def update_image(self, image: DBImage):
        """ Update the given image in the database.

            Args:
                image (DBImage): The image to update.
        """
        with self.sessionmaker() as session:
            session.merge(image)
            session.commit()


    def get_dbimage(self, collection: str, image_path: str):
        """ Returns the image and metadata for the given image path 
            within a collection.

            Args:
                collection (str): The name of the collection.
                image_path (str): The relative path to the image.

            Returns:
                DBImage: The metadata image, or None if it doesn't exist.
        """
        with self.sessionmaker() as session:
            query = (
                session.query(DBImage)
                .outerjoin(DBImageMetadata)
                .options(contains_eager(DBImage.image_metadata))
                .filter(and_(DBImage.collection == collection, DBImage.image_path == image_path))
            )
            return query.one_or_none()


    def get_dbimages(self,
            collection: str = None,
            search_string: str = '',
            filter_params: Dict[str,str] = None,
            page: int = 0,
            page_size: int = 0
        ):
        """
        Find images and metadata with optional search parameters and pagination.

        Args:
            collection (str): The name of the collection to filter by.
            search_string (str): The string to search for within image metadata.
            filter_params (Dict[str,str]): Additional filters to apply to the query.
            page (int): The one-indexed page number.
            page_size (int): The number of results per page. 0 means infinite.

        Returns:
            dict: A dictionary containing the images and pagination information.
        """
        if page < 0:
            raise ValueError("Page index must be a non-negative integer.")
        with self.sessionmaker() as session:
            query = (session
                     .query(DBImage)
                     .outerjoin(DBImageMetadata)
                     .options(contains_eager(DBImage.image_metadata))
                     )

            # Apply collection filter
            if collection:
                query = query.filter(DBImage.collection == collection)

            # Apply search filters using LIKE
            search_filters = []
            if search_string:
                search_filters.append(DBImage.path.ilike(f'%{search_string}%'))
                for column in self.column_map:
                    search_filters.append(getattr(DBImageMetadata, column).ilike(f'%{search_string}%'))

            if search_filters:
                query = query.filter(or_(*search_filters))

            # Apply additional filters
            if filter_params:
                for column, value in filter_params.items():
                    if value == "None":
                        query = query.filter(getattr(DBImageMetadata, column).is_(None))
                    elif value:
                        query = query.filter(getattr(DBImageMetadata, column).ilike(f'%{value}%'))

            # Count total results
            total_count = query.count()
            
            # Apply pagination
            offset = (page - 1) * page_size
            if page_size > 0:
                query = query.limit(page_size).offset(offset)

            images = query.all()

            # Calculate pagination attrs
            start_num = offset + 1
            
            end_num = start_num + page_size - 1
            if end_num > total_count:
                end_num = total_count
            
            total_pages = 1
            if page_size > 0:
                total_pages = (total_count + page_size - 1) // page_size  # Ceiling division

            logger.debug(f"Found {total_count} images, returning {len(images)}")
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


    def get_unique_values(self, column_name) -> Dict[str,int]:
        """ Return a map of unique values to their counts from a column.

            Args:
                column_name (str): The name of the column to get unique values from.

            Returns:
                dict: A dictionary of unique values to their counts.
        """
        with self.sessionmaker() as session:
            column = getattr(DBImageMetadata, column_name)
            results = (
                # pylint: disable=not-callable
                session.query(column, func.count().label('count'))
                .group_by(column)
                .all()
            )
            # Build the result dictionary
            value_counts = {str(row[0]): int(row[1]) for row in results}

            # Handle None values
            if None in value_counts:
                logger.debug(f"Ignoring {value_counts[None]} items with no value for {column_name}")
                del value_counts[None]

            return value_counts


    def get_unique_comma_delimited_values(self, column_name) -> Dict[str,int]:
        """ Return a map of unique values to their counts from a column whose values 
            are comma delimited lists.

            Args:
                column_name (str): The name of the column to get unique values from.

            Returns:
                dict: A dictionary of unique values to their counts.
        """
        with self.sessionmaker() as session:
            column = getattr(DBImageMetadata, column_name)

            # Retrieve all comma-delimited values from the column
            values = session.query(column).all()

            # Count unique items from comma-delimited lists
            value_counts = defaultdict(int)
            for value_tuple in values:
                value = value_tuple[0]
                if value:
                    for item in value.split(','):
                        item = item.strip()
                        value_counts[item] += 1

            return dict(value_counts)
