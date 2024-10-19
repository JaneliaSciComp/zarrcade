import io
import os

import numpy as np
import zarr
import skimage as ski
from loguru import logger
from PIL import Image
from microfilm.microplot import microshow


def adjust_brightness(img: np.ndarray, p_lower=0, p_upper=90) -> np.ndarray:
    """ Adjust the brightness of an image by stretching the histogram 
        based on the specified percentiles.
    """
    p_lower, p_upper = np.percentile(img, (p_lower, p_upper))
    return ski.exposure.rescale_intensity(img, in_range=(p_lower, p_upper))


def _make_mip(root) -> Image:
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.
    """
    multiscale = root['/'].attrs['multiscales'][0]
    datasets = multiscale['datasets']

    # get lowest res image
    dataset = datasets[-1]
    path = dataset['path']
    time_series = root[path]
    image_data = time_series[0] # TCZYX
    #print(f"Using path {path} with shape {image_data.shape}")

    # Assuming image_data is of shape (C, Z, Y, X) where C is the number of channels
    # TODO: fix this assumption
    num_channels = image_data.shape[0]
    num_slices = image_data.shape[1]  # This is the Z-axis size
    height = image_data.shape[2]      # Y dimension
    width = image_data.shape[3]       # X dimension

    # Initialize an array to hold the MIP images with shape (C, T, X, Y)
    # For this context, T is equivalent to the number of channels
    mip_images = np.empty((num_channels, 1, height, width), dtype=image_data.dtype)
    mip_image_list = []

    for c in range(num_channels):
        channel_data = image_data[c, :, :, :]  # Extract the data for channel c
        mip_image = np.max(channel_data, axis=0)  # Perform the MIP across Z-axis
        mip_image_list.append(mip_image)
        mip_images[c, 0, :, :] = mip_image 

    #print(f"MIP shape: {mip_images.shape}")

    mip = microshow(
        images=mip_images[:,0,:,:],
        fig_scaling=5,
        # TODO: read colormap from Omero metadata
        cmaps=['pure_green','pure_red', 'pure_magenta', 'pure_cyan'])
    
    #mip.savefig('mip.png')

    # We need to jump through some hoops to save the figure to a buffer 
    # in memory (instead of a file) and convert it to a numpy array, 
    # so that it can be processed further (e.g. for brightness adjustment).
    buf = io.BytesIO()
    mip.savefig(buf, format='png')
    buf.seek(0)
    with Image.open(buf) as img:
        arr = np.array(img)
        return arr


def make_mip_from_zarr(zarr_path, mip_path, p_lower=0, p_upper=90):
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.
    """
    store = zarr.DirectoryStore(zarr_path)
    root = zarr.open(store, mode='r')
    mip = _make_mip(root)
    adjusted = adjust_brightness(mip, p_lower, p_upper)
    ski.io.imsave(mip_path, adjusted)


def make_thumbnail(mip_path, thumbnail_path, thumbnail_size=300, jpeg_quality=95):
    """ Create a thumbnail from the given maximum intensity projection (MIP).
    """
    image = Image.open(mip_path)
    max_size = (thumbnail_size, thumbnail_size)
    image.thumbnail(max_size)
    aux_name, _ = os.path.splitext(mip_path)

    # Avoid "cannot write mode P as JPEG" error (e.g. when there is transparency)
    image = image.convert("RGB")

    image.save(thumbnail_path, quality=jpeg_quality)


# Test harness
if __name__ == "__main__":
    zarr_path = '/nrs/flynp/EASI-FISH_NP_SS_OMEZarr/NP11_R3_20240513/NP11_R3_3_5_SS69117_AstA_546_AstC_647_150x_Central.zarr/0'
    make_thumbnail(zarr_path, 'mip_adjusted.png')

