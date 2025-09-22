import io
import os

import numpy as np
import zarr
import skimage as ski
from skimage import exposure
from loguru import logger
from PIL import Image
from microfilm.microplot import microshow

SIMPLE_HEX_COLOR_MAP = {
    'FF0000': 'pure_red',
    '00FF00': 'pure_green',
    '0000FF': 'pure_blue',
    'FF00FF': 'pure_magenta',
    '00FFFF': 'pure_cyan',
    'FFFF00': 'pure_yellow',
    'FFFFFF': 'gray',
    'red': 'pure_red',
    'green': 'pure_green',
    'blue': 'pure_blue',
    'magenta': 'pure_magenta',
    'cyan': 'pure_cyan',
    'yellow': 'pure_yellow',
    'white': 'gray',
}

def translate_color(color: str) -> str:
    """ Attempt to translate a color from a hex string to a microfilm color name.
        If we can't then return the original color.
        See https://guiwitz.github.io/microfilm/docs/source/microfilm.html#microfilm.colorify.cmaps_def
    """
    return SIMPLE_HEX_COLOR_MAP.get(color, color)


def adjust_brightness(img: np.ndarray, p_lower=0, p_upper=90) -> np.ndarray:
    """ Adjust the brightness of an image by stretching the histogram 
        based on the specified percentiles.
    """
    p_lower, p_upper = np.percentile(img, (p_lower, p_upper))
    return ski.exposure.rescale_intensity(img, in_range=(p_lower, p_upper))


def adjust_file_brightness(src_path, dst_path):
    img = ski.io.imread(src_path)
    p_lower, p_upper = np.percentile(img, (0, 99.90))
    img_rescale = exposure.rescale_intensity(img, in_range=(p_lower, p_upper))
    ski.io.imsave(dst_path, img_rescale)


def _select_dataset(root, min_dim_size=1000):
    """ Walk backwards through datasets to find one with 
        the min dimension size in at least one direction.
    """
    multiscale = root['/'].attrs['multiscales'][0]
    selected_dataset = None
    for i in range(len(multiscale['datasets']) - 1, -1, -1):
        dataset_candidate = multiscale['datasets'][i]
        path_candidate = dataset_candidate['path']
        time_series_candidate = root[path_candidate]
        # assumes TCZYX
        image_data_candidate = time_series_candidate[0]
        
        if any(dim >= min_dim_size for dim in image_data_candidate.shape):
            selected_dataset = dataset_candidate
            logger.trace(f"Selected dataset at index {i} with shape: {image_data_candidate.shape}")
            break

    if selected_dataset is None:
        # If no dataset has the min dimension size, use the last one as fallback
        selected_dataset = multiscale['datasets'][-1]
        logger.trace(f"No dataset with shape >= {min_dim_size} found, using fallback dataset with shape: {root[selected_dataset['path']][0].shape}")

    return selected_dataset


def _make_mip(root, colors=None, min_dim_size=1000) -> Image:
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.
    """
    if not colors:
        colors = ['pure_green','pure_red', 'pure_magenta', 'pure_cyan']
    else:
        for color in colors:
            if color not in SIMPLE_HEX_COLOR_MAP:
                logger.warning(f"Unknown color: {color}")
            else:
                translated_color = translate_color(color)
                logger.trace(f"Translated color: {color} -> {translated_color}")
        colors = [translate_color(color) for color in colors]

    multiscale = root['/'].attrs['multiscales'][0]
    dataset = _select_dataset(root, min_dim_size=min_dim_size)
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
        cmaps=colors)
    
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


def make_mip_from_zarr(store, mip_path, p_lower=0, p_upper=90, colors=None):
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.
    """
    root = zarr.open(store, mode='r')
    mip = _make_mip(root, colors)
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
    zarr_path = '/nearline/flynp/EASI-FISH_NP_SS_OMEZarr/NP51_R1_20240522/NP51_R1_4_1_SS75253_Tk_546_Mip_647_036x_CentralDapi.zarr/0'
    store = zarr.DirectoryStore(zarr_path)
    make_mip_from_zarr(store, 'mip_adjusted.png', colors=['00FFFF'])
    make_thumbnail('mip_adjusted.png', 'mip_adjusted_thumbnail.jpg')

