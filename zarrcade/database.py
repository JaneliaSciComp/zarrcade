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
    metadata_columns = relationship('DBMetadataColumn', back_populates='collection')


class DBMetadataColumn(Base):
    __tablename__ = 'metadata_columns'
    id = Column(Integer, primary_key=True, autoincrement=True)
    db_name = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=False)
    collection = relationship('DBCollection', back_populates='metadata_columns')

    __table_args__ = (
        UniqueConstraint('collection_id', 'db_name', name='uq_collection_db_name'),
    )


class DBImageMetadata(Base):
    __tablename__ = 'image_metadata'
    id = Column(Integer, primary_key=True)
    path = Column(String, nullable=False)
    aux_image_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)
    images = relationship('DBImage', back_populates='image_metadata')
    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=False)
    collection = relationship('DBCollection')

    __table_args__ = (
        UniqueConstraint('collection_id', 'path', name='uq_collection_path'),
        Index('ix_collection_path', 'collection_id', 'path')
    )

class DBImage(Base):
    __tablename__ = 'images'
    id = Column(Integer, primary_key=True)
    image_path = Column(String, nullable=False, index=True)
    path = Column(String, nullable=False)
    group_path = Column(String, nullable=False)
    image_info = Column(String, nullable=False)
    image_metadata_id = Column(Integer, ForeignKey('image_metadata.id'), nullable=True, index=True)
    image_metadata = relationship('DBImageMetadata', back_populates='images')
    collection_id = Column(Integer, ForeignKey('collections.id'), nullable=False)
    collection = relationship('DBCollection')
    
    __table_args__ = (
        Index('collection_path_idx', 'collection_id', 'path'),
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

        # Read the attribute naming map from the database, organized by collection
        with self.sessionmaker() as session:
            result = session.query(DBMetadataColumn).all()
            self.column_map = defaultdict(dict)
            self.reverse_column_map = defaultdict(dict)
            
            for item in result:
                collection_id = item.collection_id
                if collection_id not in self.column_map:
                    self.column_map[collection_id] = {}
                    self.reverse_column_map[collection_id] = {}
                
                self.column_map[collection_id][item.db_name] = item.original_name
                self.reverse_column_map[collection_id][item.original_name] = item.db_name

        # Add dynamic metadata columns
        for collection_id, columns in self.column_map.items():
            for column in columns:
                if not hasattr(DBImageMetadata, column):
                    setattr(DBImageMetadata, column, Column(column, String))


    def get_column_map(self, collection_name: str) -> Dict[str,str]:
        """ Get the column map for a collection.
        """
        collection = self.collection_map[collection_name]
        return self.column_map[collection.id]


    def get_reverse_column_map(self, collection_name: str) -> Dict[str,str]:
        """ Get the reverse column map for a collection.
        """
        collection = self.collection_map[collection_name]
        return self.reverse_column_map[collection.id]


    def get_collections(self) -> List[DBCollection]:
        """ Get all collections from the database.
        """
        with self.sessionmaker() as session:
            return session.query(DBCollection).all()


    def get_table(self, table_name: str) -> Table:
        """ Get a SQLAlchemy table from the database.

            Args:
                table_name (str): The name of the table.

            Returns:
                Table: The table loaded from the database.
        """
        return Table(table_name, self.metadata, autoload_with=self.engine)


    def add_collection(self, name, settings_path) -> DBCollection:
        """ Add a new collection to the database.

            Args:
                name (str): The name of the collection.
                label (str): The human-readable label for the collection.
                data_url (str): The URL of the collection.
        """
        if name in self.collection_map:

            if self.collection_map[name].settings_path != settings_path:
                raise ValueError(f"Collection {name} already exists with a different settings path: {self.collection_map[name].settings_path}")
                
            # Collection already exists
            return

        with self.engine.connect() as connection:
            # Insert into collections
            collections = self.get_table('collections')
            insert_stmt = collections.insert().values(name=name, settings_path=settings_path)
            connection.execute(insert_stmt)
            connection.commit()

            # Fetch the inserted collection
            select_stmt = collections.select().where(collections.c.name == name)
            result = connection.execute(select_stmt).fetchone()

            # Update internal state
            self.collection_map[name] = result
            logger.info(f"Added new collection: {name} (settings_path={settings_path})")

            return result
        

    def get_collection(self, id: int) -> DBCollection:
        """ Get a collection by its ID.

            Args:
                id (int): The ID of the collection.

            Returns:
                DBCollection: The collection with the specified ID, or None if not found.
        """
        with self.engine.connect() as connection:
            collections = self.get_table('collections')
            select_stmt = collections.select().where(collections.c.id == id)
            result = connection.execute(select_stmt).fetchone()
            return result


    def delete_collection(self, collection_name: str) -> None:
        """ Delete a collection and all associated data from the database.

            Args:
                collection_name (str): The name of the collection to delete.

            Raises:
                ValueError: If the collection does not exist.
        """
        if collection_name not in self.collection_map:
            raise ValueError(f"Collection {collection_name} does not exist")

        collection_id = self.collection_map[collection_name].id
        
        with self.engine.connect() as connection:
            try:
                # Delete all associated image metadata first (due to foreign key constraints)
                image_metadata = self.get_table('image_metadata')
                delete_image_metadata_stmt = image_metadata.delete().where(
                    image_metadata.c.collection_id == collection_id
                )
                connection.execute(delete_image_metadata_stmt)
                
                # Delete all associated metadata columns
                metadata_columns = self.get_table('metadata_columns')
                delete_metadata_columns_stmt = metadata_columns.delete().where(
                    metadata_columns.c.collection_id == collection_id
                )
                connection.execute(delete_metadata_columns_stmt)
                
                # Finally delete the collection itself
                collections = self.get_table('collections')
                delete_collection_stmt = collections.delete().where(
                    collections.c.id == collection_id
                )
                connection.execute(delete_collection_stmt)
                
                connection.commit()
                
                # Update internal state
                if collection_id in self.column_map:
                    del self.column_map[collection_id]
                if collection_id in self.reverse_column_map:
                    del self.reverse_column_map[collection_id]
                del self.collection_map[collection_name]
                
                logger.info(f"Deleted collection: {collection_name} (id={collection_id})")
            except SQLAlchemyError as e:
                connection.rollback()
                logger.error(f"Error deleting collection {collection_name}: {e}")
                raise


    def add_metadata_column(self, collection_name, db_name, original_name):
        """ Add a new dynamic metadata column to the database.

            Args:
                collection_name (str): The name of the collection.
                db_name (str): The name of the new column in the database.
                original_name (str): The original name (i.e. label) of the column.
        """
        collection_id = self.collection_map[collection_name].id
        
        # Check if column already exists for this collection
        if collection_id in self.column_map and db_name in self.column_map[collection_id]:
            logger.debug(f"Column {db_name} already exists for collection {collection_name}")
            return

        with self.engine.connect() as connection:
            try:
                # Add column to the image_metadata table if it doesn't exist
                if not db_name in self.metadata.tables['image_metadata'].columns:
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
                original_name=original_name,
                collection_id=collection_id
            )
            connection.execute(insert_stmt)
            connection.commit()

            # Update internal state
            if collection_id not in self.column_map:
                self.column_map[collection_id] = {}
                self.reverse_column_map[collection_id] = {}
                
            self.column_map[collection_id][db_name] = original_name
            self.reverse_column_map[collection_id][original_name] = db_name
            self.load()
            logger.info(f"Added new metadata column: {db_name} (original={original_name}) for collection {collection_name}")
            

    def add_image_metadata(self, collection_name: str, image_metadata_rows: List[Dict[str,str]]) -> int:
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
                    # Get collection id from name
                    collection = self.collection_map[collection_name]
                    row['collection_id'] = collection.id

                    new_metadata = metadata_table.insert().values(row)
                    try:
                        session.execute(new_metadata)
                        inserted += 1
                    except IntegrityError:
                        # Try updating instead
                        update_stmt = metadata_table.update().where(
                            and_(
                                metadata_table.c.collection_id == row['collection_id'],
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


    def update_image_metadata(self, collection_name: str, metadata_id: int, updated_metadata: Dict[str, str]) -> bool:
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
                # Get collection id if collection name provided
                collection = self.collection_map[collection_name]
                updated_metadata['collection_id'] = collection.id

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


    def get_all_image_metadata(self, collection: str) -> List[DBImageMetadata]:
        """ Get all image metadata from the database.
        """
        with self.sessionmaker() as session:
            collection_id = self.collection_map[collection].id
            return session.query(DBImageMetadata).filter(DBImageMetadata.collection_id == collection_id).all()


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
            collection_id = self.collection_map[collection].id
            query = session.query(DBImageMetadata.path, DBImageMetadata.id) \
                        .filter(DBImageMetadata.collection_id == collection_id)
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
        collection_id = self.collection_map[collection].id

        with self.sessionmaker() as session:
            try:
                db_image = session.query(DBImage) \
                                  .filter_by(collection_id=collection_id, image_path=image_path) \
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
                        collection_id = collection_id,
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


    def get_dbimage(self, collection_name: str, image_path: str) -> DBImage | None:
        """ Returns the image and metadata for the given image path 
            within a collection.

            Args:
                collection (str): The name of the collection.
                image_path (str): The relative path to the image.

            Returns:
                DBImage: The metadata image, or None if it doesn't exist.
        """
        with self.sessionmaker() as session:
            collection_id = self.collection_map[collection_name].id
            query = (
                session.query(DBImage)
                .join(DBImage.collection)
                .outerjoin(DBImage.image_metadata)
                .options(contains_eager(DBImage.image_metadata))
                .options(contains_eager(DBImage.collection))
                .filter(and_(DBImage.collection_id == collection_id, DBImage.image_path == image_path))
            )
            return query.one_or_none()


    def get_dbimages(self,
            collection: str = None,
            search_string: str = '',
            filter_params: Dict[str,str] = None,
            page: int = 0,
            page_size: int = 0
        ) -> Dict:
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
                     .join(DBImage.collection)
                     .outerjoin(DBImage.image_metadata)
                     .options(contains_eager(DBImage.image_metadata))
                     .options(contains_eager(DBImage.collection))
                     )

            # Apply collection filter
            collection_id = None
            if collection:
                collection_id = self.collection_map[collection].id
                query = query.filter(DBImage.collection_id == collection_id)

            # Apply search filters using LIKE
            search_filters = []
            if search_string:
                search_filters.append(DBImage.path.ilike(f'%{search_string}%'))
                
                # Only search in columns for the specific collection
                if collection_id and collection_id in self.column_map:
                    for column in self.column_map[collection_id]:
                        search_filters.append(getattr(DBImageMetadata, column).ilike(f'%{search_string}%'))

            if search_filters:
                query = query.filter(or_(*search_filters))

            # Apply additional filters
            if filter_params and collection_id and collection_id in self.column_map:
                for column, value in filter_params.items():
                    if column in self.column_map[collection_id] or hasattr(DBImageMetadata, column):
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
            logger.debug(f"Page size: {page_size}, offset: {offset}")

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


    def get_unique_values(self, collection_name, column_name) -> Dict[str,int]:
        """ Return a map of unique values to their counts from a column.

            Args:
                collection_name (str): The name of the collection.
                column_name (str): The name of the column to get unique values from.

            Returns:
                dict: A dictionary of unique values to their counts.
        """
        with self.sessionmaker() as session:
            collection_id = self.collection_map[collection_name].id
            column = getattr(DBImageMetadata, column_name)
            results = (
                # pylint: disable=not-callable
                session.query(column, func.count().label('count'))
                .filter(DBImageMetadata.collection_id == collection_id)
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


    def get_unique_comma_delimited_values(self, collection_name, column_name) -> Dict[str,int]:
        """ Return a map of unique values to their counts from a column whose values 
            are comma delimited lists.

            Args:
                collection_name (str): The name of the collection.
                column_name (str): The name of the column to get unique values from.

            Returns:
                dict: A dictionary of unique values to their counts.
        """
        with self.sessionmaker() as session:
            collection_id = self.collection_map[collection_name].id
            column = getattr(DBImageMetadata, column_name)

            # Retrieve all comma-delimited values from the column
            values = session.query(column).filter(DBImageMetadata.collection_id == collection_id).all()

            # Count unique items from comma-delimited lists
            value_counts = defaultdict(int)
            for value_tuple in values:
                value = value_tuple[0]
                if value:
                    for item in value.split(','):
                        item = item.strip()
                        value_counts[item] += 1

            return dict(value_counts)
