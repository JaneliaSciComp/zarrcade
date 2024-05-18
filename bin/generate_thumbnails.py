#!/usr/bin/env python3

import sys
sys.path.insert(0, '.')
sys.path.insert(0, '..')

import os
import argparse
import zarr
from PIL import Image 
from loguru import logger

from zarrcade.images import yield_ome_zarrs, get_fs

parser = argparse.ArgumentParser(
    description='Generate thumbnails from PNG images stored in the same directory structure as the Zarrs')

parser.add_argument('-r', '--root_url', type=str, required=True,
    help='Path to the folder containing the images')
parser.add_argument('-t', '--thumbnail_url', type=str, required=False,
    help='Path to the folder containing thumbnail images. Default: <root_url>/.zarrcade')
parser.add_argument('-f', '--image_filename', type=str, required=False, default="zmax.png",
    help='Name of the input image filename')
    
SIZE = 300
MAX_SIZE = (SIZE, SIZE)
JPEG_QUALITY = 90

args = parser.parse_args()
root_path = args.root_url
proj_path = args.thumbnail_url or f"{root_path}/.zarrcade"
proj_filename = args.image_filename

proj_name, proj_ext = os.path.splitext(proj_filename)

fs, fsroot = get_fs(root_path)
logger.debug(f"Filesystem root is {fsroot}")

# Ensure dir ends in a path separator
fsroot_dir = os.path.join(fsroot, '')
logger.trace(f"Filesystem dir is {fsroot_dir}")
for zarr_path in yield_ome_zarrs(fs, fsroot):

    zarr_relpath = os.path.relpath(zarr_path, root_path)
    relpath, zarr_name_with_ext = os.path.split(zarr_relpath)
    zarr_name, _ = os.path.splitext(zarr_name_with_ext)
    z = zarr.open(zarr_path, mode='r')

    thumbnail_path = os.path.join(proj_path, relpath, zarr_name, proj_filename)
    image = Image.open(thumbnail_path)
    image.thumbnail(MAX_SIZE)

    sized_filename = f"{proj_name}_{SIZE}.jpg"
    sized_thumbnail_path = os.path.join(proj_path, relpath, zarr_name, sized_filename)
    
    # Avoid "cannot write mode P as JPEG" error (e.g. when there is transparency)
    image = image.convert("RGB")

    image = image.save(sized_thumbnail_path, quality=JPEG_QUALITY, optimize=True)
    print(f"Wrote {sized_thumbnail_path}")
