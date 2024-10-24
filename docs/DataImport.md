# Data Import

You can import images into Zarrcade using the provided command line script:

```bash
./bin/import.py -d /root/data/dir -c mycollection
```

This will automatically create a local Sqlite database containing a Zarrcade **collection** named "mycollection" and populate it with information about the images in the specified directory. You can also add a label to the collection by setting the `--collection-label` parameter. This label will be displayed in the web UI when choosing the collection to view.


## Annotations

You can add additional annotations to the images by providing a CSV file with the `-m` flag. The CSV file's first column must be a relative path to the OME-Zarr image within the root data directory. The remaining columns can be any annotations that will be searched and displayed within the gallery.

You can modify the service configuration to control how the annotations are displayed and searched in the gallery. See the [Configuration](./Configuration.md) section for more details.


## Auxiliary Images

By default, the import script will also create MIPs and thumbnails for each image in `./static/.zarrcade`. You can disable this by setting the `--no-aux` flag. You can change the output file location by setting the `--aux-path` parameter. Zarrcade will proxy the files automatically from within the `static` folder, but this may not be suitable for a production deployment. Instead, you can store the auxiliary images in the same directory as the OME-Zarr files. You will need to upload the files to your S3 bucket or other storage. Then, set `aux_image_mode: relative` in your `settings.yaml` to let Zarrcade know that your auxiliary files are stored relative to your data. 


## Auxiliary Image Options

Currently, Zarrcade supports creation of Maximum Intensity Projection (MIP) and thumbnails of the MIPs. You can control the brightness of the MIPs using the `--p-lower` and `--p-upper` parameters.


## Custom Auxiliary Image Generation

You can create your own auxiliary images and thumbnails by setting the `--aux-path` parameter to the location where Zarrcade should find the files. Organize the folder structure to match the OME-Zarr files, and set the `aux_image_name` and `thumbnail_name` parameters to the names of the files containing the auxiliary images and thumbnails, respectively. During the import process, Zarrcade will detect that the files exist and will not attempt to generate them.

