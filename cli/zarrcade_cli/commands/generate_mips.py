"""Generate MIPs and thumbnails from zarr containers."""

import os
import sys
import hashlib
from pathlib import Path
from typing import Optional

import click
import pandas as pd
import numpy as np
from loguru import logger

from ..core.filestore import get_filestore
from ..core.agent import yield_images
from ..core.omezarr import OmeZarrAgent
from ..core.thumbnails import make_mip_from_zarr, make_thumbnail


def get_output_path(zarr_path: str, output_dir: str, naming: str, suffix: str) -> str:
    """Generate output path for a thumbnail based on naming strategy.

    Args:
        zarr_path: Path to the zarr container
        output_dir: Base output directory
        naming: Naming strategy ('flat' or 'nested')
        suffix: File suffix (e.g., '_mip.png' or '_thumb.jpg')

    Returns:
        Full output path for the file
    """
    if naming == 'flat':
        # Use hash of path for flat naming
        path_hash = hashlib.sha256(zarr_path.encode()).hexdigest()[:16]
        filename = f"{path_hash}{suffix}"
        return os.path.join(output_dir, filename)
    else:
        # Nested naming preserves directory structure
        # Clean up the path for use as a directory structure
        clean_path = zarr_path.strip('/').replace('.zarr', '')
        subdir = os.path.join(output_dir, clean_path)
        os.makedirs(subdir, exist_ok=True)
        return os.path.join(subdir, f"thumbnail{suffix.replace('_thumb', '').replace('_mip', '')}")


@click.command()
@click.argument('input_path', type=str, required=False)
@click.option('-o', '--output', 'output_dir', type=click.Path(), required=True,
              help='Output directory for thumbnails (required)')
@click.option('--input-csv', type=click.Path(exists=True),
              help='Read zarr paths from CSV file (first column)')
@click.option('--base-url', type=str, default=None,
              help='Base URL to resolve relative zarr paths')
@click.option('--naming', type=click.Choice(['flat', 'nested']), default='flat',
              help='Output naming strategy: flat (hash-based) or nested (path-based)')
@click.option('--thumbnail-size', type=int, default=300,
              help='Thumbnail size in pixels (default: 300)')
@click.option('--mip-size', type=int, default=None,
              help='Minimum XY dimension for resolution selection (default: thumbnail-size)')
@click.option('--skip-existing', is_flag=True, default=False,
              help='Skip if output already exists')
@click.option('--output-csv', type=click.Path(),
              help='Write output CSV with thumbnail paths')
@click.option('--thumbnail-column', type=str, default='thumbnail_url',
              help='Column name for thumbnail paths (default: thumbnail_url)')
# MIP parameters
@click.option('--clahe-limit', type=float, default=0.02,
              help='CLAHE clip limit (default: 0.02)')
@click.option('--p-lower', type=float, default=0.1,
              help='Lower percentile for contrast stretching (default: 0.1)')
@click.option('--p-upper', type=float, default=99.5,
              help='Upper percentile for contrast stretching (default: 99.5)')
@click.option('--max-gain', type=float, default=8.0,
              help='Maximum gain for contrast stretching (default: 8.0)')
@click.option('--target-max', type=int, default=65535,
              help='Target max value (default: 65535 for 16-bit)')
@click.option('--ignore-zeros', is_flag=True, default=False,
              help='Ignore zero pixels when computing percentiles')
@click.option('--k-bg', type=float, default=-np.inf,
              help='Background floor threshold in MADs (default: -inf, disabled)')
@click.option('--min-dynamic', type=float, default=1e-6,
              help='Minimum dynamic range (default: 1e-6)')
@click.option('--max-depth', type=int, default=10,
              help='Maximum directory depth to search (default: 10)')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Enable verbose logging')
def mips(input_path: Optional[str], output_dir: str, input_csv: Optional[str],
         base_url: Optional[str], naming: str, thumbnail_size: int, mip_size: int,
         skip_existing: bool, output_csv: Optional[str], thumbnail_column: str,
         clahe_limit: float, p_lower: float, p_upper: float, max_gain: float,
         target_max: int, ignore_zeros: bool, k_bg: float, min_dynamic: float,
         max_depth: int, verbose: bool):
    """Generate MIPs and thumbnails from zarr containers.

    INPUT_PATH is the directory to scan (local path or s3:// URI).
    Alternatively, use --input-csv to read paths from a CSV file.

    Examples:

        zarrcade mips /data/zarrs -o /thumbnails --naming flat

        zarrcade mips --input-csv images.csv -o /thumbnails --output-csv images-with-thumbs.csv

        zarrcade mips s3://bucket/zarrs -o /thumbnails --base-url https://bucket.s3.amazonaws.com/zarrs
    """
    # Configure logging
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    # Validate input
    if not input_path and not input_csv:
        raise click.UsageError("Either INPUT_PATH or --input-csv must be provided")

    # Default mip_size to thumbnail_size
    if mip_size is None:
        mip_size = thumbnail_size

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Build stretch kwargs
    stretch_kwargs = {
        'p_lower': p_lower,
        'p_upper': p_upper,
        'max_gain': max_gain,
        'target_max': target_max,
        'ignore_zeros': ignore_zeros,
        'k_bg': k_bg,
        'min_dynamic': min_dynamic,
    }

    results = []

    if input_csv:
        # Read paths from CSV
        logger.info(f"Reading zarr paths from {input_csv}")
        df = pd.read_csv(input_csv, sep=None, engine='python')  # Auto-detect delimiter
        path_column = df.columns[0]  # First column is the path
        paths = df[path_column].tolist()

        # Keep the original dataframe for output
        original_df = df.copy()

        for i, zarr_path in enumerate(paths):
            logger.info(f"Processing [{i+1}/{len(paths)}]: {zarr_path}")

            # Resolve path if base_url provided
            if base_url:
                full_path = os.path.join(base_url.rstrip('/'), zarr_path.lstrip('/'))
            else:
                full_path = zarr_path

            # Process this zarr
            result = process_zarr(
                full_path, output_dir, naming, thumbnail_size, mip_size,
                skip_existing, clahe_limit, stretch_kwargs
            )

            if result:
                results.append({
                    'path': zarr_path,
                    'thumbnail_path': result['thumbnail_path'],
                    'mip_path': result['mip_path'],
                })

        # Update original CSV with thumbnail paths
        if output_csv and results:
            # Create a mapping from path to thumbnail
            thumb_map = {r['path']: r['thumbnail_path'] for r in results}
            original_df[thumbnail_column] = original_df[path_column].map(thumb_map)
            original_df.to_csv(output_csv, index=False)
            logger.info(f"Wrote {len(original_df)} rows to {output_csv}")

    else:
        # Discover zarrs from directory
        logger.info(f"Discovering zarr containers in {input_path}")

        fs = get_filestore(input_path)
        agents = [OmeZarrAgent()]

        discovered = list(yield_images(fs, agents, path='', maxdepth=max_depth))
        logger.info(f"Found {len(discovered)} zarr container(s)")

        for i, (zarr_path, image) in enumerate(discovered):
            logger.info(f"Processing [{i+1}/{len(discovered)}]: {zarr_path}")

            # Build full path
            if base_url:
                full_path = os.path.join(base_url.rstrip('/'), zarr_path.lstrip('/'))
            else:
                full_path = os.path.join(input_path, zarr_path)

            # Get channel colors from image metadata
            colors = None
            if image.channels:
                colors = [c.color for c in image.channels]

            # Process this zarr
            result = process_zarr(
                full_path, output_dir, naming, thumbnail_size, mip_size,
                skip_existing, clahe_limit, stretch_kwargs, colors
            )

            if result:
                results.append({
                    'path': zarr_path,
                    'name': os.path.basename(zarr_path.rstrip('/')),
                    'thumbnail_path': result['thumbnail_path'],
                    'mip_path': result['mip_path'],
                })

        # Write output CSV
        if output_csv and results:
            df = pd.DataFrame(results)
            df.to_csv(output_csv, index=False)
            logger.info(f"Wrote {len(df)} rows to {output_csv}")

    logger.info(f"Generated {len(results)} thumbnail(s)")


def process_zarr(zarr_path: str, output_dir: str, naming: str,
                 thumbnail_size: int, min_dim_size: int, skip_existing: bool,
                 clahe_limit: float, stretch_kwargs: dict,
                 colors: list = None) -> Optional[dict]:
    """Process a single zarr container to generate MIP and thumbnail.

    Returns:
        Dictionary with 'mip_path' and 'thumbnail_path', or None on error
    """
    try:
        # Generate output paths
        mip_path = get_output_path(zarr_path, output_dir, naming, '_mip.png')
        thumbnail_path = get_output_path(zarr_path, output_dir, naming, '_thumb.jpg')

        # Skip if exists
        if skip_existing and os.path.exists(thumbnail_path):
            logger.debug(f"Skipping existing: {thumbnail_path}")
            return {
                'mip_path': mip_path,
                'thumbnail_path': thumbnail_path,
            }

        # Ensure output directory exists (for nested naming)
        os.makedirs(os.path.dirname(mip_path), exist_ok=True)

        # Get filestore and store
        fs = get_filestore(zarr_path)
        store = fs.get_store('')

        # Generate MIP
        logger.debug(f"Generating MIP: {mip_path}")
        make_mip_from_zarr(
            store, mip_path,
            adjust_channel_brightness=True,
            colors=colors,
            clahe_limit=clahe_limit,
            min_dim_size=min_dim_size,
            **stretch_kwargs
        )

        # Generate thumbnail
        logger.debug(f"Generating thumbnail: {thumbnail_path}")
        make_thumbnail(mip_path, thumbnail_path, thumbnail_size=thumbnail_size)

        return {
            'mip_path': mip_path,
            'thumbnail_path': thumbnail_path,
        }

    except Exception as e:
        logger.error(f"Failed to process {zarr_path}: {e}")
        return None
