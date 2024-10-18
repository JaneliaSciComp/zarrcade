# Configuration

You can configure Zarrcade by editing the `settings.yaml` file, or by setting environment variables. Environment variables will override settings in the `settings.yaml` file.

The following configuration options are available:

`base_url` or `BASE_URL`: The base URL for the Zarrcade service. This is used to generate URLs for the images and other resources in the service. 

`db_url` or `DB_URL`: The URL of the database to use for the Zarrcade service. This can be a SQLite database, a PostgreSQL database, or other database supported by SQLAlchemy.

`title_column_name` or `TITLE_COLUMN_NAME`: The name of the column in the image metadata that contains the title of the image. This is used to display the title of the image in the image list and other places.

`filters` or `FILTERS`: A list of filters to apply to the images. Filters are used to select a subset of the images in the service. 

`log_level` or `LOG_LEVEL`: The log level to use for the Zarrcade service. This can be `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.

`debug_sql` or `DEBUG_SQL`: If true, SQLAlchemy queries will be logged at the `DEBUG` level.

`exclude_paths` or `EXCLUDE_PATHS`: A list of paths to exclude from the Zarrcade service. This can be used to exclude directories from the service.

