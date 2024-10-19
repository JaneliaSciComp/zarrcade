import pytest
from zarrcade.database import Database, DBImageMetadata, DBImage
from zarrcade.model import Image


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def db(db_url):
    db = Database(db_url)
    yield db
    db.engine.dispose()


def test_database_initialization(db):
    assert isinstance(db, Database)
    assert db.engine is not None
    assert db.sessionmaker is not None


def test_add_collection(db):
    db.add_collection("test_collection", "Test Collection", "/path/to/data")
    assert "test_collection" in db.collection_map
    assert db.collection_map["test_collection"].data_url == "/path/to/data"
    assert db.collection_map["test_collection"].label == "Test Collection"


def test_add_metadata_column(db):
    db.add_metadata_column("test_column", "Test Column")
    assert "test_column" in db.column_map
    assert db.column_map["test_column"] == "Test Column"


def test_add_image_metadata(db):
    db.add_metadata_column("color", "Color")
    db.add_collection("test_collection", "Test Collection", "test_url")
    metadata_rows = [
        {"collection": "test_collection", "path": "test_path", "color": "red"}
    ]
    inserted = db.add_image_metadata(metadata_rows)
    assert inserted == 1
    
    # Test inserting duplicate row (should not increase count)
    inserted = db.add_image_metadata(metadata_rows)
    assert inserted == 0

    # Test inserting new row
    new_metadata_row = [
        {"collection": "test_collection", "path": "test_path2", "color": "blue"}
    ]
    inserted = db.add_image_metadata(new_metadata_row)
    assert inserted == 1

    # Verify both rows are now in the database
    with db.sessionmaker() as session:
        all_rows = session.query(DBImageMetadata).filter_by(collection="test_collection").all()
        assert len(all_rows) == 2
        assert set(row.path for row in all_rows) == {"test_path", "test_path2"}
        assert set(row.color for row in all_rows) == {"red", "blue"}


def test_persist_image(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    image = Image(relative_path="test_image.png", group_path="")
    db.persist_image("test_collection", image, None)

    with db.sessionmaker() as session:
        db_image = session.query(DBImage).filter_by(collection="test_collection", image_path="test_image.png").first()
        assert db_image is not None
        assert db_image.path == "test_image.png"
        assert db_image.group_path == ""
        assert db_image.get_image() == image

def test_persist_images(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    db.add_metadata_column("color", "Color")
    
    metadata_rows = [
        {"collection": "test_collection", "path": "test_path1/0", "color": "red"},
        {"collection": "test_collection", "path": "test_path2/0", "color": "blue"},
        {"collection": "test_collection", "path": "test_path3/0", "color": "red"}
    ]
    inserted = db.add_image_metadata(metadata_rows)
    assert inserted == 3

    def image_generator():
        images = [
            Image(relative_path="test_path1", group_path="/0"),
            Image(relative_path="test_path2", group_path="/0"),
            Image(relative_path="test_path3", group_path="/0"),
            Image(relative_path="test_path4", group_path="/0")
        ]
        for image in images:
            yield image

    persisted_count = db.persist_images("test_collection", image_generator, only_with_metadata=True)
    assert persisted_count == 3

    with db.sessionmaker() as session:
        all_images = session.query(DBImage).filter_by(collection="test_collection").all()
        assert len(all_images) == 3
        assert set(image.image_path for image in all_images) == {"test_path1/0", "test_path2/0", "test_path3/0"}

    persisted_count = db.persist_images("test_collection", image_generator, only_with_metadata=False)
    assert persisted_count == 4

    with db.sessionmaker() as session:
        all_images = session.query(DBImage).filter_by(collection="test_collection").all()
        assert len(all_images) == 4
        assert set(image.image_path for image in all_images) == {"test_path1/0", "test_path2/0", "test_path3/0", "test_path4/0"}


def test_get_dbimage(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    image = Image(relative_path="test_image.png", group_path="")
    db.persist_image("test_collection", image, None)

    metaimage = db.get_dbimage("test_collection", "test_image.png")
    assert metaimage is not None
    assert metaimage.image_path == "test_image.png"


def test_metadata_search(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    db.add_metadata_column("color", "Color")
    
    metadata_rows = [
        {"collection": "test_collection", "path": "test_path1", "color": "red"},
        {"collection": "test_collection", "path": "test_path2", "color": "blue"},
        {"collection": "test_collection", "path": "test_path3", "color": "red"}
    ]

    inserted = db.add_image_metadata(metadata_rows)
    assert inserted == 3

    with db.sessionmaker() as session:
        ims = session.query(DBImageMetadata).filter_by(collection="test_collection").all()
        for im in ims:
            image = Image(relative_path=im.path, group_path="/0")
            db.persist_image("test_collection", image, im.id)
    
    result = db.get_dbimages("test_collection", filter_params={"color": "red"})
    assert len(result['images']) == 2
    assert set(image.image_path for image in result['images']) == {"test_path1/0", "test_path3/0"}

    result = db.get_dbimages("test_collection", search_string="blue")
    assert len(result['images']) == 1
    assert result['images'][0].image_path == "test_path2/0"


def test_pagination(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    num_images = 10
    for i in range(1, num_images+1):
        image = Image(relative_path=f"test_image{i}.png", group_path="/test")
        db.persist_image("test_collection", image, None)

    count = db.get_images_count()
    assert count == num_images

    result = db.get_dbimages("test_collection", page=1, page_size=10)
    print(result)
    assert len(result['images']) == 10
    assert result['pagination']['total_count'] == num_images

    result = db.get_dbimages("test_collection", page=1, page_size=3)
    assert len(result['images']) == 3
    assert result['pagination']['page'] == 1
    assert result['pagination']['page_size'] == 3
    assert result['pagination']['total_pages'] == 4
    assert result['pagination']['total_count'] == num_images
    assert result['pagination']['start_num'] == 1
    assert result['pagination']['end_num'] == 3

    result = db.get_dbimages("test_collection", page=4, page_size=3)
    assert len(result['images']) == 1
    assert result['pagination']['page'] == 4
    assert result['pagination']['page_size'] == 3
    assert result['pagination']['total_pages'] == 4
    assert result['pagination']['total_count'] == num_images
    assert result['pagination']['start_num'] == 10
    assert result['pagination']['end_num'] == 10
    

def test_get_unique_values(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    db.add_metadata_column("test_column", "Test Column")
    
    metadata_rows = [
        {"collection": "test_collection", "path": "test_path1", "test_column": "value1"},
        {"collection": "test_collection", "path": "test_path2", "test_column": "value2"},
        {"collection": "test_collection", "path": "test_path3", "test_column": "value1"}
    ]
    db.add_image_metadata(metadata_rows)

    unique_values = db.get_unique_values("test_column")
    assert unique_values == {"value1": 2, "value2": 1}


def test_get_unique_comma_delimited_values(db):
    db.add_collection("test_collection", "Test Collection", "test_url")
    db.add_metadata_column("test_column", "Test Column")
    
    metadata_rows = [
        {"collection": "test_collection", "path": "test_path1", "test_column": "value1"},
        {"collection": "test_collection", "path": "test_path2", "test_column": "value2,value3"},
        {"collection": "test_collection", "path": "test_path3", "test_column": "value1,value4"}
    ]
    db.add_image_metadata(metadata_rows)

    unique_values = db.get_unique_comma_delimited_values("test_column")
    assert unique_values == {"value1": 2, "value2": 1, "value3": 1, "value4": 1}