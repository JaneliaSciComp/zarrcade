import io
import os

import numpy as np
import zarr
import skimage as ski
from loguru import logger
from PIL import Image
from microfilm.microplot import microshow
from microfilm import colorify
import matplotlib

SIMPLE_HEX_COLOR_MAP = {
    'red': '#FF0000',
    'green': '#00FF00',
    'blue': '#0000FF',
    'magenta': '#FF00FF',
    'cyan': '#00FFFF',
    'yellow': '#FFFF00',
    'orange': '#FF8000',
    'white': '#FFFFFF',
}

def adjust_brightness(img: np.ndarray, p_lower=0, p_upper=90) -> np.ndarray:
    """ Adjust the brightness of an image by stretching the histogram 
        based on the specified percentiles.
    """
    p_lower, p_upper = np.percentile(img, (p_lower, p_upper))
    return ski.exposure.rescale_intensity(img, in_range=(p_lower, p_upper))


def adjust_file_brightness(src_path, dst_path):
    img = ski.io.imread(src_path)
    p_lower, p_upper = np.percentile(img, (0, 99.90))
    img_rescale = ski.exposure.rescale_intensity(img, in_range=(p_lower, p_upper))
    ski.io.imsave(dst_path, img_rescale)



def stretch_with_max_gain(channel, p_lower=0.1, p_upper=99.9, max_gain=8, target_max=65535):
    """
    Stretch a single image channel to the full range, but limit the maximum gain.

    Parameters
    ----------
    channel : np.ndarray
        2D array for a single channel (e.g., one fluorescence color).
    p_lower : float
        Lower percentile for contrast stretching (default: 0.1).
    p_upper : float
        Upper percentile for contrast stretching (default: 99.9).
    max_gain : float
        Maximum allowed gain (e.g., 8-32). Limits how much a narrow range can be amplified.
    target_max : int
        Target maximum value (65535 for 16-bit output, 255 for 8-bit).

    Returns
    -------
    np.ndarray
        Contrast-stretched channel with gain capped.
    """
    # Convert to float for safe math
    ch_float = channel.astype(np.float32)

    # Compute lower and upper percentiles
    lo = np.percentile(ch_float, p_lower)
    hi = np.percentile(ch_float, p_upper)
    logger.trace(f"Lower percentile: {lo}, Upper percentile: {hi}")

    # Calculate the range, ensuring it's not zero
    dynamic_range = max(hi - lo, 1e-6)
    logger.trace(f"Dynamic range: {dynamic_range}")

    # Calculate the stretch gain
    gain = target_max / dynamic_range
    logger.trace(f"Gain: {gain}")

    if gain>max_gain:
        logger.trace(f"Gain is too high, capping at {max_gain}")

    # Cap the gain if it's too high
    gain = min(gain, max_gain)

    # Apply the stretch
    stretched = (ch_float - lo) * gain

    # Clip to the valid range
    stretched = np.clip(stretched, 0, target_max)

    return stretched.astype(np.uint16)


def _select_dataset(root, min_dim_size):
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


def _make_mip(root, colors=None, min_dim_size=1024, adjust_channel_brightness=True, p_lower=0, p_upper=99.5, clahe_limit=0.02) -> Image:
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.
    """
    if not colors:
        colors = SIMPLE_HEX_COLOR_MAP.values()
    else:
        # Ensure colors are in hex format, add # if missing
        processed_colors = []
        for color in colors:
            if color.startswith('#'):
                processed_colors.append(color)
            elif len(color) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color):
                processed_colors.append(f'#{color}')
            else:
                # If it's a named color, try to convert to hex
                hex_color = SIMPLE_HEX_COLOR_MAP.get(color, None)
                if hex_color:
                    processed_colors.append(hex_color)
                else:
                    logger.warning(f"Could not convert color '{color}' to hex format, using default white")
                    processed_colors.append(SIMPLE_HEX_COLOR_MAP['white'])
        colors = processed_colors

    multiscale = root['/'].attrs['multiscales'][0]
    dataset = _select_dataset(root, min_dim_size)
    path = dataset['path']
    time_series = root[path]
    image_data = time_series[0] # TCZYX

    # Assuming image_data is of shape (C, Z, Y, X) where C is the number of channels
    # TODO: fix this assumption
    num_channels = image_data.shape[0]
    num_slices = image_data.shape[1]  # This is the Z-axis size
    height = image_data.shape[2]      # Y dimension
    width = image_data.shape[3]       # X dimension

    # Create MIP for each channel
    mip_image_list = []
    for c in range(num_channels):
        channel_data = image_data[c, :, :, :]  # Extract the data for channel c
        mip_image = np.max(channel_data, axis=0)  # Perform the MIP across Z-axis
        if adjust_channel_brightness:
            logger.trace(f"Adjusting channel brightness for channel {c} with p_lower={p_lower} and p_upper={p_upper}")
            # Stretch the contrast with a maximum gain to avoid blowing out the image
            mip_image = stretch_with_max_gain(mip_image, p_lower, p_upper)
            # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to improve contrast
            mip_image = ski.exposure.equalize_adapthist(mip_image, clip_limit=clahe_limit)

        mip_image_list.append(mip_image)

    # Use colorify_by_hex to create colored versions of each channel
    colored_images = []
    for i, mip_image in enumerate(mip_image_list):
        # Get the color for this channel, cycling through available colors
        color_hex = colors[i % len(colors)]

        # Colorify the image using the hex color
        colored_image, _, _ = colorify.colorify_by_hex(mip_image, cmap_hex=color_hex)
        colored_images.append(colored_image)
        logger.trace(f"Channel {i} colored with {color_hex}")

    # Combine all colored images into a single multi-color image
    if len(colored_images) == 1:
        combined_image = colored_images[0]
    else:
        combined_image = colorify.combine_image(colored_images)

    # Create a matplotlib figure to display the combined image
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.imshow(combined_image)
    ax.axis('off')

    # We need to jump through some hoops to save the figure to a buffer
    # in memory (instead of a file) and convert it to a numpy array,
    # so that it can be processed further (e.g. for brightness adjustment).
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close(fig)  # Close the figure to free up memory
    buf.seek(0)
    with Image.open(buf) as img:
        arr = np.array(img)
        return arr


def make_mip_from_zarr(store, mip_path, adjust_channel_brightness=True, colors=None, p_lower=0, p_upper=99.5, clahe_limit=0.02):
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.
    """
    root = zarr.open(store, mode='r')
    mip = _make_mip(root, colors,
        adjust_channel_brightness=adjust_channel_brightness,
        p_lower=p_lower,
        p_upper=p_upper,
        clahe_limit=clahe_limit
    )
    if not adjust_channel_brightness:
        # If we didn't adjust the channel brightness, adjust the overall brightness of the MIP
        logger.trace(f"Adjusting overall brightness of MIP with p_lower={p_lower} and p_upper={p_upper}")
        mip = adjust_brightness(mip, p_lower, p_upper)
    ski.io.imsave(mip_path, mip)


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
    make_mip_from_zarr(store, 'mip_adjusted.png', colors=['cyan'], adjust_channel_brightness=True, p_lower=0, p_upper=99.5)
    make_thumbnail('mip_adjusted.png', 'mip_adjusted_thumbnail.jpg')

