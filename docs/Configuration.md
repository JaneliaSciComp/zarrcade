# Configuration

You can configure Zarrcade by editing the `settings.yaml` file, or by setting environment variables. Environment variables are named with the prefix `zarrcade_` and will override settings in the `settings.yaml` file. These settings affect both the CLI scripts (e.g. `import.py`) and the web service.

The following configuration options are available:

`log_level`: The logging level to use for the Zarrcade service. This can be `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Default: `INFO`

`base_url`: The base URL for the Zarrcade service. This is used to generate URLs for the images and other resources in the service. It's required when using the build-in file proxy. Default: `http://127.0.0.1:8000/`

`database`: The database settings:
* `db_url`: The URL of the database to use for the Zarrcade service. This can be a SQLite database, a PostgreSQL database, or other database supported by SQLAlchemy. Default: `sqlite:///database.db`
* `debug_sql`: If true, SQLAlchemy queries will be logged at the `DEBUG` level.

`proxies`: A list of file proxies to use for the Zarrcade service. This can be used to proxy images from non-public storage backends, on a per-collection basis. Each proxy configuration is a dictionary with the following keys:
* `collection`: The name of the collection to use for the Zarrcade service.
* `url` or `URL`: Browser-accessible URL of the proxy.

`exclude_paths`: A list of path patterns to exclude when discovering images. These can be Git-style wildcards like `**/*.n5`. Excluding certain paths can be used to speed up the image discovery process.

`filters`: A list of filters to apply to the images. Filters are used to select a subset of the images in the service. Each filter is a dictionary with the following keys:
* `column_name`: The name of the column in the image annotation table.
* `data_type`: The type of the data in the column. This can be `string` or `csv`. When `csv`, the filter will be a dropdown with one option per unique value in each CSV value. Default: `string`.
* `filter_type`: How to display the filter in the UI. Currently, this can only be `dropdown`. Default: `dropdown`.

`title_column_name`: The name of the column in the annotations table that contains the title of the image. This is used to display the title of the image in the image gallery and other places. It may contain HTML markup, such as colors and links.

`hide_columns`: A list of annotation table columns to hide when displaying the image details page. 

Example `settings.yaml` file:

```yaml
log_level: INFO

base_url: https://localhost:8888

database:
  url: sqlite:///database.db
  debug_sql: False

proxies:
  - collection: easifish_np_ss
    url: https://rokickik-dev.int.janelia.org/nrs-flynp-omezarr/

exclude_paths:
  - "*.n5"
  - "*align"
  - "mag1"
  - "raw"
  - "dat"
  - "tiles_destreak"

filters:
  - column_name: "Driver line"
    data_type: string
    filter_type: dropdown
  - column_name: "Probes"
    data_type: csv
    filter_type: dropdown
  - column_name: "Region"
  - column_name: "Zoom"

title_column_name: "Image Name"

hide_columns:
  - "Probes"
  - "Image Name"
```
