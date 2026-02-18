"""Discover zarr containers and output metadata CSV."""

import os
import sys
from typing import Optional

import click
import pandas as pd
from loguru import logger

from ..core.filestore import get_filestore
from ..core.agent import yield_images
from ..core.omezarr import OmeZarrAgent


@click.command()
@click.argument('path', type=str)
@click.option('-o', '--output', type=click.Path(), default=None,
              help='Output CSV file path (default: stdout)')
@click.option('--base-url', type=str, default=None,
              help='Base URL for zarr data (prepended to relative paths to create URIs)')
@click.option('--format', 'output_format', type=click.Choice(['csv', 'tsv']), default='csv',
              help='Output format (default: csv)')
@click.option('--include-metadata', is_flag=True, default=False,
              help='Include zarr metadata columns (dimensions, channels, etc.)')
@click.option('--exclude', 'exclude_patterns', multiple=True,
              help='Exclude paths matching pattern (can be repeated)')
@click.option('--max-depth', type=int, default=10,
              help='Maximum directory depth to search (default: 10)')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Enable verbose logging')
def discover(path: str, output: Optional[str], base_url: Optional[str],
             output_format: str, include_metadata: bool,
             exclude_patterns: tuple, max_depth: int, verbose: bool):
    """Discover zarr containers and output metadata CSV.

    PATH is the directory to scan (local path or s3:// URI).

    Examples:

        zarrcade discover /data/zarrs -o images.csv

        zarrcade discover s3://bucket/zarrs -o images.csv --base-url https://bucket.s3.amazonaws.com/zarrs

        zarrcade discover /data/zarrs --include-metadata --format tsv
    """
    # Configure logging
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    logger.info(f"Discovering zarr containers in {path}")

    # Set up filestore
    fs = get_filestore(path)

    # Set up agents
    agents = [OmeZarrAgent()]

    # Discover images
    rows = []
    for zarr_path, image in yield_images(
        fs, agents, path='', maxdepth=max_depth, exclude_paths=list(exclude_patterns)
    ):
        logger.debug(f"Found image at {zarr_path} with group {image.group_path}")

        # Build row data
        row = {
            'path': zarr_path,
            'name': os.path.basename(zarr_path.rstrip('/')),
            'group_path': image.group_path,
        }

        # Add URI if base_url provided
        if base_url:
            row['uri'] = os.path.join(base_url.rstrip('/'), zarr_path.lstrip('/'))

        # Add metadata if requested
        if include_metadata:
            row['axes_order'] = image.axes_order
            row['dimensions'] = image.dimensions
            row['dimensions_voxels'] = image.dimensions_voxels
            row['voxel_sizes'] = image.voxel_sizes
            row['chunk_size'] = image.chunk_size
            row['num_channels'] = image.num_channels
            row['num_timepoints'] = image.num_timepoints
            row['dtype'] = image.dtype
            row['compression'] = image.compression

            # Add channel colors as comma-separated list
            if image.channels:
                row['channel_colors'] = ','.join(c.color for c in image.channels)
                row['channel_names'] = ','.join(c.name for c in image.channels)

        rows.append(row)

    if not rows:
        logger.warning("No zarr containers found")
        return

    logger.info(f"Found {len(rows)} zarr container(s)")

    # Create DataFrame
    df = pd.DataFrame(rows)

    # Determine output
    delimiter = '\t' if output_format == 'tsv' else ','

    if output:
        df.to_csv(output, sep=delimiter, index=False)
        logger.info(f"Wrote {len(rows)} rows to {output}")
    else:
        # Write to stdout
        df.to_csv(sys.stdout, sep=delimiter, index=False)
