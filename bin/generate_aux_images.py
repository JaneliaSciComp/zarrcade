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

from PIL import Image
# from loguru import logger
from zarrcade.images import yield_ome_zarrs, get_fs

JPEG_QUALITY = 90

def apply_clahe_to_image(src_path, dst_path, clip_limit=2.0, tile_grid_size=(8, 8)):
    """ Function to apply CLAHE to an image.
    """
    # pylint: disable-next=import-outside-toplevel
    import cv2

    # Read from source
    img = cv2.imread(src_path)

    # Convert the image to YUV color space
    yuv = cv2.cvtColor(img, cv2.COLOR_BGR2YUV)
    y = yuv[:,:,0]  # Extract the Y channel (brightness)

    # Apply CLAHE to the Y channel
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    y_clahe = clahe.apply(y)

    # Update the Y channel with the CLAHE output
    yuv[:,:,0] = y_clahe

    # Convert back to BGR color space
    img_clahe = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR)

    # Save to destination
    cv2.imwrite(dst_path, img_clahe)


@ray.remote
def process_zarr(zarr_path, root_path, aux_path, aux_paths, \
        aux_image_name, thumbnail_size, apply_clahe):
    """ Process auxiliary images for the given zarr.
    """

    # NP31_R3_20240220/NP31_R3_2_4_SS59799_CCHa1_546_CCHa2_647_120x_Central.zarr
    zarr_relpath = os.path.relpath(zarr_path, root_path)

    # NP31_R3_20240220, NP31_R3_2_4_SS59799_CCHa1_546_CCHa2_647_120x_Central.zarr
    relpath, zarr_name_with_ext = os.path.split(zarr_relpath)

    # NP31_R3_2_4_SS59799_CCHa1_546_CCHa2_647_120x_Central
    zarr_name, _ = os.path.splitext(zarr_name_with_ext)

    # Auxiliary image path
    aux_path_dst = os.path.join(aux_path, relpath, zarr_name, aux_image_name)

    # Copy aux image into the aux store
    if zarr_path in aux_paths:
        aux_path_src = aux_paths[zarr_path]
        os.makedirs(os.path.dirname(aux_path_dst), exist_ok=True)

        if apply_clahe:
            apply_clahe_to_image(aux_path_src, aux_path_dst)
            print(f"Wrote CLAHE-corrected {aux_path_dst}")
        else:
            shutil.copy2(aux_path_src, aux_path_dst)
            print(f"Wrote {aux_path_dst}")
    else:
        print(f"No aux path for {zarr_relpath}")
        #TODO: generate MIP
        return 0

    image = Image.open(aux_path_dst)
    max_size = (thumbnail_size, thumbnail_size)
    aux_name, _ = os.path.splitext(aux_image_name)
    image.thumbnail(max_size)
    sized_filename = f"{aux_name}_{thumbnail_size}.jpg"
    sized_thumbnail_path = os.path.join(aux_path, relpath, zarr_name, sized_filename)

    # Avoid "cannot write mode P as JPEG" error (e.g. when there is transparency)
    image = image.convert("RGB")

    image.save(sized_thumbnail_path, quality=JPEG_QUALITY, optimize=True)
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
    parser.add_argument('-r', '--root_url', type=str, required=True,
        help='Path to the folder containing the images')
    parser.add_argument('-a', '--aux-path', type=str, default=".zarrcade",
        help='Path to the folder containing auxiliary images, relative to the root_url.')
    parser.add_argument('--aux-image-name', type=str, default='zmax.png',
        help='Filename of the main auxiliary image.')
    parser.add_argument('--thumbnail-size', type=int, default=300,
        help='Max size of the thumbnail image.')
    parser.add_argument('--apply-clahe', type=bool, default=True,
        help='Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to the images. Requires OpenCV2.')
    parser.add_argument('--cores', type=int, default=4, \
        help='Number of CPU cores to use.')
    parser.add_argument('--cluster', type=str, default=None, \
        help='Connect to existing Ray cluster, e.g. 123.45.67.89:10001')
    parser.add_argument('--dashboard', type=bool, default=False, \
        help='Run the Ray dashboard for debugging.')

    # Parse arguments
    args = parser.parse_args()
    thumbnail_size = args.thumbnail_size
    root_path = args.root_url
    aux_path = os.path.join(root_path, args.aux_path)

    aux_paths = {}
    if args.csv_path:
        df = pd.read_csv(args.csv_path)
        aux_paths = dict(zip(df['zarr_path'], df['aux_path']))
        print(f"Read {len(aux_paths)} auxiliary paths from provided CSV file")

    fs, fsroot = get_fs(root_path)
    print(f"Filesystem root is {fsroot}")

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

    # Ensure dir ends in a path separator
    fsroot_dir = os.path.join(fsroot, '')
    print(f"Filesystem dir is {fsroot_dir}")

    total_count = 0
    try:
        unfinished = []
        for zarr_path in yield_ome_zarrs(fs, fsroot):
            unfinished.append(process_zarr.remote(zarr_path, root_path, aux_path, \
                aux_paths, args.aux_image_name, thumbnail_size, args.apply_clahe))
        while unfinished:
            finished, unfinished = ray.wait(unfinished, num_returns=1)
            for result in ray.get(finished):
                if result:
                    total_count += result
    finally:
        print(f"Generated auxiliary images for {total_count} zarrs")
