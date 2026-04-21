"""Embed thumbnails into zarr containers using the thumbnails convention."""

import io
import os
import sys
from typing import Optional

import click
import fsspec
import numpy as np
import pandas as pd
import skimage as ski
from loguru import logger
from PIL import Image

from ..core.filestore import get_filestore
from ..core.zarr_thumbnails import (
    CONVENTION_NAME,
    SOFTWARE_URL,
    build_entry,
    guess_media_type,
    load_root_metadata,
    register,
)


def _resolve(path: str, base_url: Optional[str]) -> str:
    """Resolve a path against an optional base URL."""
    if base_url and not (path.startswith(("s3://", "http://", "https://", "/"))):
        return os.path.join(base_url.rstrip("/"), path.lstrip("/"))
    return path


def _read_image_bytes(uri: str) -> bytes:
    """Read the raw bytes of an image from any fsspec-supported URI."""
    with fsspec.open(uri, mode="rb") as f:
        return f.read()


def _downsample_with_brightness(
    src_bytes: bytes,
    size: int,
    jpeg_quality: int,
    p_lower: float,
    p_upper: float,
) -> tuple[bytes, int, int]:
    """Load an image from bytes, adjust brightness via percentile stretch,
    resize so the longest edge is `size`, and return JPEG bytes plus final
    (width, height).
    """
    with Image.open(io.BytesIO(src_bytes)) as img:
        img = img.convert("RGB")
        arr = np.asarray(img)

    lo, hi = np.percentile(arr, (p_lower, p_upper))
    if hi > lo:
        arr = ski.exposure.rescale_intensity(arr, in_range=(lo, hi))

    out = Image.fromarray(arr)
    out.thumbnail((size, size))
    width, height = out.size

    buf = io.BytesIO()
    out.save(buf, format="JPEG", quality=jpeg_quality)
    return buf.getvalue(), width, height


def _image_dimensions(src_bytes: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(src_bytes)) as img:
        return img.size  # (width, height)


@click.command()
@click.option("--input-csv", type=click.Path(exists=True), required=True,
              help="CSV file with zarr paths in column 1 and thumbnail paths in column 2")
@click.option("--zarr-base-url", type=str, default=None,
              help="Base URL to resolve relative zarr paths")
@click.option("--thumbnail-base-url", type=str, default=None,
              help="Base URL to resolve relative thumbnail paths")
@click.option("--size", type=int, default=300, show_default=True,
              help="Longest edge (pixels) for the downsampled thumbnail")
@click.option("--jpeg-quality", type=int, default=95, show_default=True,
              help="JPEG quality for the downsampled thumbnail")
@click.option("--p-lower", type=float, default=0.0, show_default=True,
              help="Lower percentile for brightness stretching")
@click.option("--p-upper", type=float, default=99.9, show_default=True,
              help="Upper percentile for brightness stretching")
@click.option("--skip-existing", is_flag=True, default=False,
              help="Skip zarrs that already have thumbnails convention metadata")
@click.option("-v", "--verbose", is_flag=True, default=False,
              help="Enable verbose logging")
def embed(input_csv: str, zarr_base_url: Optional[str],
          thumbnail_base_url: Optional[str], size: int, jpeg_quality: int,
          p_lower: float, p_upper: float, skip_existing: bool, verbose: bool):
    """Embed thumbnails into zarr containers using the thumbnails convention.

    Reads a CSV with zarr paths in the first column and existing thumbnail
    paths in the second column. For each row:

    \b
      1. Copies the source thumbnail to <zarr>/thumbnails/thumbnail.<ext>
      2. Generates a downsampled, brightness-adjusted JPEG at
         <zarr>/thumbnails/thumbnail_<SIZE>.jpg
      3. Registers both in the zarr root's attrs per the thumbnails
         convention (https://github.com/clbarnes/zarr-convention-thumbnails)
    """
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if verbose else "INFO")

    df = pd.read_csv(input_csv, sep=None, engine="python")
    if df.shape[1] < 2:
        raise click.UsageError("Input CSV must have at least 2 columns (zarr path, thumbnail path)")

    zarr_col, thumb_col = df.columns[0], df.columns[1]
    logger.info(f"Read {len(df)} rows; using columns '{zarr_col}' (zarr) and '{thumb_col}' (thumbnail)")

    n_ok = 0
    n_fail = 0
    for i, row in df.iterrows():
        zarr_path = str(row[zarr_col])
        thumb_path = row[thumb_col]
        if pd.isna(thumb_path) or not str(thumb_path).strip():
            logger.warning(f"[{i+1}/{len(df)}] No thumbnail for {zarr_path}, skipping")
            continue
        thumb_path = str(thumb_path)

        zarr_uri = _resolve(zarr_path, zarr_base_url)
        thumb_uri = _resolve(thumb_path, thumbnail_base_url)
        logger.info(f"[{i+1}/{len(df)}] {zarr_uri}")

        try:
            _embed_one(
                zarr_uri, thumb_uri, size, jpeg_quality,
                p_lower, p_upper, skip_existing,
            )
            n_ok += 1
        except Exception as e:
            logger.error(f"Failed to embed thumbnail for {zarr_uri}: {e}")
            n_fail += 1

    logger.info(f"Embedded {n_ok} thumbnail(s), {n_fail} failure(s)")


def _embed_one(zarr_uri: str, thumb_uri: str, size: int, jpeg_quality: int,
               p_lower: float, p_upper: float, skip_existing: bool) -> None:
    fs = get_filestore(zarr_uri)
    store = fs.get_store("")

    # Verify the zarr root exists BEFORE writing anything. fsspec's mapper
    # creates parent directories on write, so a missing zarr would otherwise
    # end up as an empty directory with just a thumbnails/ subdir when
    # register() fails below.
    attrs, _, _ = load_root_metadata(store)

    if skip_existing and CONVENTION_NAME in attrs:
        logger.debug("Existing thumbnails metadata found, skipping")
        return

    src_bytes = _read_image_bytes(thumb_uri)
    src_ext = os.path.splitext(thumb_uri)[1].lower()
    if not src_ext:
        raise ValueError(f"Thumbnail has no file extension: {thumb_uri}")

    orig_path = f"thumbnails/thumbnail{src_ext}"
    down_path = f"thumbnails/thumbnail_{size}.jpg"

    orig_w, orig_h = _image_dimensions(src_bytes)
    logger.debug(f"Original thumbnail: {orig_w}x{orig_h} → {orig_path}")
    store[orig_path] = src_bytes

    down_bytes, down_w, down_h = _downsample_with_brightness(
        src_bytes, size, jpeg_quality, p_lower, p_upper,
    )
    logger.debug(f"Downsampled thumbnail: {down_w}x{down_h} → {down_path}")
    store[down_path] = down_bytes

    entries = [
        build_entry(
            path=down_path,
            width=down_w,
            height=down_h,
            description=f"Downsampled thumbnail ({size}px longest edge)",
            attributes={
                "software_url": SOFTWARE_URL,
                "p_lower": p_lower,
                "p_upper": p_upper,
                "jpeg_quality": jpeg_quality,
            },
        ),
        build_entry(
            path=orig_path,
            width=orig_w,
            height=orig_h,
            media_type=guess_media_type(orig_path),
            description="Full-resolution source thumbnail",
            attributes={
                "original_filename": os.path.basename(thumb_uri),
            },
        ),
    ]
    register(store, entries)
    logger.debug("Registered thumbnails in .zattrs")
