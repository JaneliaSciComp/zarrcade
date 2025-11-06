import io
import os

import zarr
import matplotlib
import numpy as np
import skimage as ski
from loguru import logger
from PIL import Image
from microfilm.microplot import microshow
from microfilm import colorify
from scipy.stats import median_abs_deviation as mad

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



def stretch_with_max_gain_bg_guard(
    channel,
    p_lower=0.1,
    p_upper=99.9,
    max_gain=8.0,
    target_max=65535,
    ignore_zeros=False,
    k_bg=-np.inf,       # how many MADs above the black level we consider "background floor"
    min_dynamic=1e-6
):
    """
    Stretch a single image channel with background guarding.

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
    ignore_zeros : bool
        If True, ignore zeros when computing percentiles (default: False).
    k_bg : float
        How many MADs above the black level we consider "background floor" (default: -np.inf, disabled).
    min_dynamic : float
        Minimum dynamic range to prevent division by zero (default: 1e-6).

    Returns
    -------
    np.ndarray
        Contrast-stretched channel with gain capped.
    """
    ch = channel.astype(np.float32)

    # Optionally ignore zeros which otherwise swamp the lower percentile
    if ignore_zeros:
        vals = ch[ch > 0]
        if vals.size == 0:
            return np.zeros_like(channel, dtype=np.uint16)
    else:
        vals = ch

    logger.trace(f"Using {vals.size} non-zero values out of {ch.size} total values")

    # Estimate black level from the dark tail (robust)
    # Take the bottom 5% to get a dark subset, compute its median and MAD
    dark_cut = np.percentile(vals, 5.0)
    dark_vals = vals[vals <= dark_cut]
    if dark_vals.size == 0:
        dark_vals = vals  # fallback

    black_med = np.median(dark_vals)
    black_mad = mad(dark_vals, scale='normal')  # ~= sigma for Gaussian

    # Calculate black floor, handling -inf case to avoid NaN warnings
    if np.isneginf(k_bg):
        black_floor = -np.inf
    else:
        black_floor = black_med + k_bg * (black_mad if np.isfinite(black_mad) else 0.0)
    logger.trace(f"Black floor: {black_floor}")

    # Compute percentiles on nonzero vals
    lo_p = np.percentile(vals, p_lower)
    hi_p = np.percentile(vals, p_upper)
    logger.trace(f"Lower percentile: {lo_p}, Upper percentile: {hi_p}")

    # Use the larger of the two for the lower bound so we don't raise dark background
    lo = max(lo_p, black_floor)
    hi = max(hi_p, lo + min_dynamic)
    logger.trace(f"Lower bound: {lo}, Upper bound: {hi}")

    dynamic_range = max(hi - lo, min_dynamic)
    logger.trace(f"Dynamic range: {dynamic_range}")

    # Calculate the stretch gain
    gain = target_max / dynamic_range
    logger.trace(f"Gain: {gain}")

    # Cap the gain if it's too high
    if gain>max_gain:
        logger.trace(f"Gain is too high, capping at {max_gain}")
        gain = max_gain

    stretched = (ch - lo) * gain
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


def _make_mip(root, colors=None, min_dim_size=1024, adjust_channel_brightness=True, clahe_limit=0.02, **stretch_kwargs) -> Image:
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.

    Parameters
    ----------
    root : zarr.Group
        The root zarr group.
    colors : list, optional
        List of colors for each channel.
    min_dim_size : int
        Minimum dimension size for selecting the dataset.
    adjust_channel_brightness : bool
        Whether to adjust channel brightness.
    clahe_limit : float
        Clip limit for CLAHE (Contrast Limited Adaptive Histogram Equalization).
    **stretch_kwargs : dict
        Additional keyword arguments to pass to stretch_with_max_gain_bg_guard.
        Supported parameters: p_lower, p_upper, max_gain, target_max, ignore_zeros, k_bg, min_dynamic

    Returns
    -------
    np.ndarray
        MIP image as numpy array.
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
            logger.trace(f"Adjusting channel brightness for channel {c} with stretch_kwargs={stretch_kwargs}")
            # Stretch the contrast with a maximum gain to avoid blowing out the image
            mip_image = stretch_with_max_gain_bg_guard(mip_image, **stretch_kwargs)
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


def make_mip_from_zarr(store, mip_path, adjust_channel_brightness=True, colors=None, clahe_limit=0.02, **stretch_kwargs):
    """ Create a maximum intensity projection (MIP) from an OME-Zarr image.

    Parameters
    ----------
    store : zarr.storage.Store
        The zarr storage.
    mip_path : str
        Output path for the MIP image.
    adjust_channel_brightness : bool
        Whether to adjust channel brightness.
    colors : list, optional
        List of colors for each channel.
    clahe_limit : float
        Clip limit for CLAHE (Contrast Limited Adaptive Histogram Equalization).
    **stretch_kwargs : dict
        Additional keyword arguments to pass to stretch_with_max_gain_bg_guard.
        Supported parameters: p_lower, p_upper, max_gain, target_max, ignore_zeros, k_bg, min_dynamic
    """
    root = zarr.open(store, mode='r')
    mip = _make_mip(root, colors,
        adjust_channel_brightness=adjust_channel_brightness,
        clahe_limit=clahe_limit,
        **stretch_kwargs
    )
    if not adjust_channel_brightness:
        # If we didn't adjust the channel brightness, adjust the overall brightness of the MIP
        p_lower = stretch_kwargs.get('p_lower', 0.1)
        p_upper = stretch_kwargs.get('p_upper', 99.9)
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
    make_mip_from_zarr(store, 'mip_adjusted.png', colors=['cyan'], adjust_channel_brightness=True,
                       p_lower=0.1, p_upper=99.9, max_gain=8.0)
    make_thumbnail('mip_adjusted.png', 'mip_adjusted_thumbnail.jpg')

