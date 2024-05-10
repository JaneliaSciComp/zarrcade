import json
import pandas as pd

from loguru import logger
from dataclasses import asdict
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, Integer, Index, ForeignKey, func, select

from .model import Image, MetadataImage

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


def deserialize_image_info(image_info: str):
    return Image(**json.loads(image_info))

def serialize_image_info(image: Image):
    return json.dumps(asdict(image))


class Database:

    def __init__(self, db_url: str):

        # Initialize database
        self.engine = create_engine(db_url)
        self.meta = MetaData()
        self.meta.reflect(bind=self.engine)

        # Read the attribute naming map from the database, if they exist
        self.attr_map = {}
        try:
            query = "SELECT * FROM metadata_columns"
            result_df = pd.read_sql_query(query, con=self.engine)
            for row in result_df.itertuples():
                db_name = row.db_name
                original_name = row.original_name
                print(f"Registering column '{db_name}' for {original_name}")
                self.attr_map[db_name] = original_name
        except:
            logger.info("No metadata columns defined")

        # Create empty metadata table if necessary

        self.metadata_table = Table('metadata', self.meta,
            Column('id', Integer, primary_key=True),  # Autoincrements by default in many DBMS
            Column('collection', String, nullable=False),
            Column('relpath', String, nullable=False),
            extend_existing=True
        )
        self.meta.create_all(self.engine)

        # Create image table if necessary
        self.images_table = Table('images', self.meta,
            Column('id', Integer, primary_key=True),
            Column('collection', String, nullable=False),
            Column('relpath', String, nullable=False),
            Column('dataset', String, nullable=False),
            Column('image_path', String, nullable=False, index=True),
            Column('image_info', String, nullable=False),
            Column('metadata_id', Integer, ForeignKey('metadata.id', ondelete='SET NULL'), nullable=True, index=True),
            Index('collection_relpath_idx', 'collection', 'relpath'),
            extend_existing=True)
        self.meta.create_all(self.engine)


    def get_tuple_metadata(self, row):
        metadata = {}
        for k in self.attr_map:
            if k in row._fields:
                metadata[self.attr_map[k]] = getattr(row, k)
        return metadata


    def get_images_count(self):
        with self.engine.begin() as conn:
            query = select(func.count()) \
                .select_from(self.images_table) \
                .where(self.images_table.c.image_info.isnot(None))
            result = conn.execute(query)
            return result.scalar()


    def get_relpath_to_metadata_id_map(self, collection: str):
        metadata_ids = {}
        query = "SELECT id,relpath FROM metadata WHERE collection = :collection"
        result_df = pd.read_sql_query(query, con=self.engine, params={'collection': collection})
        for row in result_df.itertuples():
            metadata_ids[row.relpath] = row.id
        return metadata_ids


    def persist_image(self, collection: str, relpath: str, 
                      dataset: str, image: Image, metadata_id: int):
        image_path = f"{relpath}{dataset}"
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
                    values(relpath=relpath,
                            dataset=dataset,
                            image_info=image_info,
                            metadata_id=metadata_id)
                conn.execute(update_stmt)
                logger.info(f"Updated {image_path}")
            else:
                insert_stmt = self.images_table.insert() \
                        .values(collection=collection, 
                                relpath=relpath, 
                                dataset=dataset, 
                                image_path=image_path, 
                                image_info=image_info, 
                                metadata_id=metadata_id)
                conn.execute(insert_stmt)
                logger.info(f"Inserted {image_path}")


    def get_metaimage(self, image_path: str):
        full_query = text(f"{IMAGES_AND_METADATA_SQL} WHERE i.image_path = :image_path")
        result_df = pd.read_sql_query(full_query, con=self.engine, params={'image_path': image_path})
        for row in result_df.itertuples():
            relpath = row.relpath
            image_info_json = row.image_info
            logger.info(f"Found {row.image_path} in image collection")
            if image_info_json:
                image = deserialize_image_info(image_info_json)
                metadata = self.get_tuple_metadata(row)
                metaimage = MetadataImage(relpath, image, metadata)
                return metaimage
            else:
                logger.info(f"Image has no image_info: {image_path}")
                return None
            
        logger.info(f"Image not found: {image_path}")
        return None


    def find_metaimages(self, search_string: str):
        full_query = IMAGES_AND_METADATA_SQL
        if not search_string: 
            result_df = pd.read_sql_query(full_query, con=self.engine)
        else:
            cols = [f"m.{k}" for k in self.attr_map.keys()] or ['i.relpath']
            query_string = " OR ".join([f"{col} LIKE :search_string" for col in cols])
            full_query = text(f"{full_query} WHERE {query_string}")
            result_df = pd.read_sql_query(full_query, con=self.engine, params={'search_string': '%'+search_string+'%'})

        images = []
        for row in result_df.itertuples():
            metadata = self.get_tuple_metadata(row)
            image_info_json = row.image_info
            image_path = row.image_path
            if image_info_json:
                image = deserialize_image_info(image_info_json)
                metaimage = MetadataImage(image_path, image, metadata)
                logger.info(f"  adding {metaimage.id}")
                images.append(metaimage)

        return images