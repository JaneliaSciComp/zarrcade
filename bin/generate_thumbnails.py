#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, '..')

import zarr
from PIL import Image 
from loguru import logger

from zarrcade.images import yield_ome_zarrs, get_fs

SIZE = 300
MAX_SIZE = (SIZE, SIZE)

root_path = "/nearline/flynp/EASI-FISH_NP_SS_OMEZarr"
proj_path = f"{root_path}/.zarrcade"
proj_filename = "zmax.png"

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
    image.convert("RGB").save(sized_thumbnail_path)
    print(f"Saved to {sized_thumbnail_path}")
