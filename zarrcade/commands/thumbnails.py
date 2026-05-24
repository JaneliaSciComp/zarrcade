"""Resize raster images into smaller JPEG thumbnails."""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from loguru import logger

from ..core.thumbnails import make_thumbnail


@click.command()
@click.argument('input_dir', type=click.Path(exists=True, file_okay=False))
@click.option('-o', '--output', 'output_dir', type=click.Path(),
              help='Output directory for JPEG thumbnails (default: same as INPUT_DIR)')
@click.option('--pattern', type=str, default='*.png', show_default=True,
              help='Glob pattern for input files within INPUT_DIR')
@click.option('--size', 'thumbnail_size', type=int, default=300, show_default=True,
              help='Max width/height in pixels (aspect-preserving)')
@click.option('--quality', type=int, default=90, show_default=True,
              help='JPEG quality (1-95); ignored for PNG output')
@click.option('--format', 'out_format',
              type=click.Choice(['jpg', 'png']), default='jpg', show_default=True,
              help='Output format. PNG is lossless and often better for fluorescence MIPs.')
@click.option('--suffix', type=str, default='', show_default=True,
              help='Suffix to append to the basename (e.g. "_thumb")')
@click.option('--overwrite', is_flag=True, default=False,
              help='Overwrite existing JPEGs')
@click.option('-v', '--verbose', is_flag=True, default=False,
              help='Enable verbose logging')
def thumbnails(input_dir: str, output_dir: Optional[str], pattern: str,
               thumbnail_size: int, quality: int, out_format: str,
               suffix: str, overwrite: bool, verbose: bool):
    """Resize raster images into smaller JPEG thumbnails.

    Walks INPUT_DIR for files matching --pattern and writes a resized JPEG
    for each one, preserving aspect ratio. Defaults to writing into
    INPUT_DIR alongside the originals.

    Examples:

        zarrcade thumbnails /data/Thumbnails

        zarrcade thumbnails /data/Thumbnails --size 400 --quality 80 --suffix _thumb
    """
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
    else:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    in_dir = Path(input_dir)
    out_dir = Path(output_dir) if output_dir else in_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = sorted(in_dir.glob(pattern))
    if not inputs:
        logger.warning(f"No files matching {pattern!r} in {in_dir}")
        return

    logger.info(f"Found {len(inputs)} input file(s) in {in_dir}")

    written = 0
    skipped = 0
    failed = 0
    for i, src in enumerate(inputs, 1):
        dst = out_dir / f"{src.stem}{suffix}.{out_format}"
        # Guard against overwriting the source when in_dir == out_dir and
        # the input already has an extension matching the output.
        if dst.resolve() == src.resolve():
            logger.warning(f"[{i}/{len(inputs)}] skip (would overwrite source): {src}")
            skipped += 1
            continue
        if dst.exists() and not overwrite:
            logger.debug(f"[{i}/{len(inputs)}] skip (exists): {dst}")
            skipped += 1
            continue
        try:
            make_thumbnail(str(src), str(dst),
                           thumbnail_size=thumbnail_size,
                           jpeg_quality=quality)
            size_kb = os.path.getsize(dst) / 1024
            logger.info(f"[{i}/{len(inputs)}] wrote {dst.name} ({size_kb:.0f} KB)")
            written += 1
        except Exception as e:
            logger.error(f"[{i}/{len(inputs)}] failed for {src}: {e}")
            failed += 1

    logger.info(f"Done: {written} written, {skipped} skipped, {failed} failed")
