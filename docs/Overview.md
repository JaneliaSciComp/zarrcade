# Zarrcade Overview

## Data Model

Zarrcade uses a simple database schema to store the image metadata and annotations. A DBCollection is a named collection of images discovered at a particular URL. Images in the collection are added to the DBImage table. Annotations optionally loaded from the user-provided CSV file are added to the DBImageMetadata table, and each DBImage may be linked to a DBImageMetadata record. Columns in the CSV file are added to the DBMetadataColumn table which maps the original column name to the internal database name.

### Class diagram

```mermaid
classDiagram

class DBCollection {
    int id
    String name
    String label
    String data_url
}

class DBMetadataColumn {
    int id
    String db_name
    String original_name
}

class DBImageMetadata {
    int id
    String collection
    String path
    String aux_image_path
    String thumbnail_path
    String YOUR_ANNOTATION_NAME
}

class DBImage {
    int id
    String collection
    String image_path
    String path
    String group_path
    String image_info
    int image_metadata_id
}

DBImageMetadata "1" --> "0..*" DBImage : contains
DBImage "1" --> "0..1" DBImageMetadata : references
DBCollection "1" --> "0..*" DBImage : contains
```

### Entity-relationship (ER) diagram

```mermaid
erDiagram
DBCollection {
    id int
    name str
    label str
    data_url str
}

DBMetadataColumn {
    id int
    db_name str
    original_name str
}

DBImageMetadata {
    id int
    collection str
    path str
    aux_image_path str
    thumbnail_path str
}

DBImage {
    id int
    collection str
    image_path str
    path str
    group_path str
    image_info str
    image_metadata_id int
}

DBCollection ||--o{ DBImageMetadata : contains
DBImageMetadata ||--o{ DBImage : contains
DBImage ||--o| DBImageMetadata : references

```

