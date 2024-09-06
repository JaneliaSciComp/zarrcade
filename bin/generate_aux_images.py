#!/usr/bin/env python3
"""
Generate auxiliary images for Zarrcade. 

Walks a Zarrcade root path and generates 2d auxiliary images which can be 
viewed in the Zarrcade web interface. 

Optionally ingests existing images by providing a CSV file with paths to 
the existing images.
"""
import sys
sys.path.insert(0, '.')
sys.path.insert(0, '..')

import os
import shutil
import argparse

import pandas as pd
import ray
import skimage as ski
from skimage import exposure
import numpy as np
from PIL import Image

from zarrcade import Database, get_filestore
from zarrcade.settings import get_settings
from zarrcade.images import yield_ome_zarrs

JPEG_QUALITY = 95

def adjust_brightness(src_path, dst_path):
    img = ski.io.imread(src_path)
    p_lower, p_upper = np.percentile(img, (0, 99.90))
    img_rescale = exposure.rescale_intensity(img, in_range=(p_lower, p_upper))
    ski.io.imsave(dst_path, img_rescale)


@ray.remote
def process_zarr(rel_zarr_path:str, data_path:str, aux_data_path:str, aux_path_map:dict, \
        aux_image_name:str, thumbnail_size:int, apply_brightness_adj:bool):
    """ Process auxiliary images for the given zarr.
    """
    # NP31_R3_20240220, NP31_R3_2_4_SS59799_CCHa1_546_CCHa2_647_120x_Central.zarr
    relpath, zarr_name_with_ext = os.path.split(rel_zarr_path)

    # NP31_R3_2_4_SS59799_CCHa1_546_CCHa2_647_120x_Central
    zarr_name, _ = os.path.splitext(zarr_name_with_ext)

    # Auxiliary image path
    aux_path_dst = os.path.join(aux_data_path, relpath, zarr_name, aux_image_name)

    # Auxiliary image name (without extension)
    aux_name, _ = os.path.splitext(aux_image_name)

    if rel_zarr_path in aux_path_map:
        aux_path_src = aux_path_map[rel_zarr_path]
        if not os.path.exists(aux_path_dst):
            # Copy aux image into the aux store
            os.makedirs(os.path.dirname(aux_path_dst), exist_ok=True)
            shutil.copy2(aux_path_src, aux_path_dst)
            print(f"Wrote {aux_path_dst}")

    else:
        #TODO: generate MIP
        print(f"No aux path for {rel_zarr_path}")
        return 0

    if apply_brightness_adj:
        bc_filename = f"{aux_name}_bc.png"
        aux_path_dst = os.path.join(aux_data_path, relpath, zarr_name, bc_filename)
        adjust_brightness(aux_path_src, aux_path_dst)
        print(f"Wrote brightness-corrected {aux_path_dst}")

    image = Image.open(aux_path_dst)
    max_size = (thumbnail_size, thumbnail_size)
    image.thumbnail(max_size)
    sized_filename = f"{aux_name}_{thumbnail_size}.jpg"
    sized_thumbnail_path = os.path.join(aux_data_path, relpath, zarr_name, sized_filename)

    # Avoid "cannot write mode P as JPEG" error (e.g. when there is transparency)
    image = image.convert("RGB")

    image.save(sized_thumbnail_path, quality=JPEG_QUALITY)
    print(f"Wrote {sized_thumbnail_path}")
    return 1


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('-c', '--csv-path', type=str,
        help='Path to a CSV file containing a mapping of zarr paths to auxiliary images. ' + \
            'The file should have two columns: zarr_path,aux_path')
    parser.add_argument('-a', '--aux-path', type=str, default=".zarrcade",
        help='Path to the folder containing auxiliary images, relative to the root_url.')
    parser.add_argument('--aux-image-name', type=str, default='zmax.png',
        help='Filename of the main auxiliary image.')
    parser.add_argument('--thumbnail-size', type=int, default=300,
        help='Max size of the thumbnail image.')
    parser.add_argument('--apply-brightness-correction', type=bool, default=True,
        help='Apply brightness correction to the images.')
    parser.add_argument('--cores', type=int, default=4, \
        help='Number of CPU cores to use.')
    parser.add_argument('--cluster', type=str, default=None, \
        help='Connect to existing Ray cluster, e.g. 123.45.67.89:10001')
    parser.add_argument('--dashboard', type=bool, default=False, \
        help='Run the Ray dashboard for debugging.')

    # Read settings from environment or YAML
    settings = get_settings()
    # TODO: this assumes that data resides on a local filesystem
    data_path = str(settings.data_url)

    # Parse arguments
    args = parser.parse_args()
    thumbnail_size = args.thumbnail_size
    aux_data_path = os.path.join(data_path, args.aux_path)

    aux_path_map = {}
    if args.csv_path:
        df = pd.read_csv(args.csv_path)
        for zarr_path, aux_path in zip(df['zarr_path'], df['aux_path']):
            if not zarr_path.startswith(data_path):
                print(f"Warning: Zarr path is outside of data_url: {zarr_path}")
            else:
                relative_zarr_path = os.path.relpath(zarr_path, data_path)
                aux_path_map[relative_zarr_path] = aux_path
        print(f"Mapped {len(aux_path_map)} auxiliary paths from provided CSV file")

    # Initialize Ray
    cpus = args.cores
    if cpus:
        print(f"Using {cpus} cores")

    if "head_node" in os.environ:
        head_node = os.environ["head_node"]
        port = os.environ["port"]
        address = f"{head_node}:{port}"
    else:
        address = f"{args.cluster}" if args.cluster else None

    if address:
        print(f"Using cluster: {address}")

    include_dashboard = args.dashboard
    dashboard_port = 8265
    if include_dashboard:
        print(f"Deploying dashboard on port {dashboard_port}")

    ray.init(num_cpus=cpus,
            include_dashboard=include_dashboard,
            dashboard_host='0.0.0.0',
            dashboard_port=dashboard_port,
            address=address)

    fs = get_filestore(data_path)

    total = 0
    generated = 0
    try:
        unfinished = []
        for rel_zarr_path in yield_ome_zarrs(fs):
            unfinished.append(process_zarr.remote(rel_zarr_path, data_path, aux_data_path, \
                aux_path_map, args.aux_image_name, thumbnail_size, args.apply_brightness_correction))
            total += 1
        while unfinished:
            finished, unfinished = ray.wait(unfinished, num_returns=1)
            for result in ray.get(finished):
                if result:
                    generated += result
    finally:
        print(f"Generated auxiliary images for {generated}/{total} zarrs")
