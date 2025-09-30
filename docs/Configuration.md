# Configuration

## Configuring collections

Each data collection in Zarrcade needs a YAML file which describes how the data is found and presented in the web UI. There are two main ways to load in Zarr images:
1) **Run image discovery** - During the import step, Zarrcade will walk a filesystem to find all Zarr images and import them automatically. This method uses the `discovery` settings below. When using image discovery, any image paths in the `metadata_path` file should be relative to the `data_url`.
2) **Provide absolute URIs** - You provide an absolute path to each Zarr container or image. This method uses the `metadata_path` below.

All of the possible collection settings are listed below.

`label`: UI label for the collection
`discovery`: Discovery settings
  * `data_url`: The top-level URL that will be walked to find images. Can be a local path or S3 URI. 
  * `exclude_paths`: Paths to exclude when discovering images in the data URL. Supports git-style wildcards like `**/*.tiff`.
  * `proxy_url`: The URL of the proxy server. If provided, the relative image paths will be fetched via the proxy server. 
`metadata_file`: Path to a CSV or TSV file which provides metadata about images. See the [Metadata File](#metadata) section below for more information.
`aux_image_mode`: This setting controls how auxiliary images (e.g. thumbnails) are found, with these possible values:
  * `static` - treat paths as relative to the `./static` folder
  * `absolute` - treat paths as absolute 
  * `relative` - uses paths relative to the `data_url`
`title_column_name`: *(DEPRECATED: Use `title_template` instead)* The name of the column in the annotations table that contains the title of the image. This is used to display the title of the image in the image gallery and other places. It may contain HTML markup, such as colors and links.
`title_template`: String template for building image titles. Can contain references to any column name using curly braces (e.g., `{column_name}`) and can include HTML markup such as `<font>` tags. For example: `<font color="red">{Line}</font> - {Marker}`. If both `title_template` and `title_column_name` are provided, `title_template` takes precedence.
`filters`: A list of filters to apply to the images. Filters are used to select a subset of the images in the service. Each filter is a dictionary with the following keys:
  * `column_name`: The name of the column in the image annotation table.
  * `data_type`: The type of the data in the column. This can be `string` or `csv`. When `csv`, the filter will be a dropdown with one option per unique value in each CSV value. Default: `string`.
  * `filter_type`: How to display the filter in the UI. Currently, this can only be `dropdown`. Default: `dropdown`.
`hide_columns`: A list of annotation table columns to hide when displaying the image details page. 


## Metadata file

The metadata file is used to provide arbitrary metadata for each image. It may be in CSV (comma-separated value) or TSV (tab-separated value) format. 

This file's first column must be the path to the OME-Zarr image. If using `discovery`, then this path must be relative to the `data_url`, otherwise it must be absolute. 
If any column contains `thumbnail` (case-sensitive), then it will be imported as the aux path for the image. 
The remaining columns may be any annotations which will be made searchable and displayed within the gallery, e.g.:

```csv
Path,Line,Marker
relative/path/to/ome1.zarr,JKF6363,Blu
relative/path/to/ome2.zarr,JDH3562,Blu
```

