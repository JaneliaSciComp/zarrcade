"""Zarr Thumbnail Convention support.

Implements https://github.com/clbarnes/zarr-convention-thumbnails
(UUID: 49326c01-1180-4743-b15f-f7157038a6ab)

Reads and writes attrs directly against the store so it works on both
zarr v2 (`.zattrs`) and zarr v3 (`zarr.json`) without depending on a
particular zarr-python major version.
"""

import json
import os
from typing import Optional

CONVENTION_NAME = "thumbnails"
CONVENTION_UUID = "49326c01-1180-4743-b15f-f7157038a6ab"
CONVENTION_SPEC_URL = "https://github.com/clbarnes/zarr-convention-thumbnails"
CONVENTION_SCHEMA_URL = (
    "https://raw.githubusercontent.com/zarr-conventions/thumbnails/"
    "refs/tags/v1/schema.json"
)
SOFTWARE_URL = "https://github.com/JaneliaSciComp/zarrcade"

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


def guess_media_type(path: str) -> str:
    """Return the MIME type for a thumbnail path based on its extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext not in MEDIA_TYPES:
        raise ValueError(f"Unsupported thumbnail extension: {ext}")
    return MEDIA_TYPES[ext]


def build_entry(
    path: str,
    width: int,
    height: int,
    media_type: Optional[str] = None,
    description: Optional[str] = None,
    attributes: Optional[dict] = None,
) -> dict:
    """Build a thumbnail entry matching the convention schema."""
    if ".." in path.split("/") or "." in path.split("/"):
        raise ValueError(f"Thumbnail path must not contain '.' or '..' segments: {path}")
    entry = {
        "width": int(width),
        "height": int(height),
        "media_type": media_type or guess_media_type(path),
        "path": path,
    }
    if description:
        entry["description"] = description
    if attributes:
        entry["attributes"] = attributes
    return entry


def _get_bytes(store, key: str) -> Optional[bytes]:
    try:
        return store[key]
    except KeyError:
        return None


def load_root_metadata(store) -> tuple[dict, str, Optional[dict]]:
    """Load the root node's user attrs.

    Returns (attrs, zarr_format, raw_v3_meta). `zarr_format` is "v2" or "v3".
    For v3, `raw_v3_meta` is the full parsed `zarr.json`; for v2 it is None.
    """
    raw_v3 = _get_bytes(store, "zarr.json")
    if raw_v3 is not None:
        meta = json.loads(raw_v3)
        if meta.get("zarr_format") == 3:
            return dict(meta.get("attributes", {})), "v3", meta

    raw_zattrs = _get_bytes(store, ".zattrs")
    if raw_zattrs is not None:
        return json.loads(raw_zattrs), "v2", None

    # v2 node without user attrs yet
    if _get_bytes(store, ".zgroup") is not None or _get_bytes(store, ".zarray") is not None:
        return {}, "v2", None

    raise ValueError(
        "No zarr root metadata found at store root "
        "(expected .zattrs, .zgroup, .zarray, or zarr.json)"
    )


def save_root_attrs(store, attrs: dict, zarr_format: str,
                    raw_v3_meta: Optional[dict]) -> None:
    """Write the full user attrs dict back to the appropriate metadata file."""
    if zarr_format == "v3":
        if raw_v3_meta is None:
            raise ValueError("v3 format requires raw_v3_meta from load_root_metadata")
        meta = dict(raw_v3_meta)
        meta["attributes"] = attrs
        store["zarr.json"] = json.dumps(meta, indent=2).encode("utf-8")
    else:
        store[".zattrs"] = json.dumps(attrs, indent=2).encode("utf-8")


def has_thumbnails(store) -> bool:
    """Return True if the store's root already has a `thumbnails` attr."""
    attrs, _, _ = load_root_metadata(store)
    return CONVENTION_NAME in attrs


def register(store, entries: list) -> None:
    """Write the thumbnail entries to the zarr root's attrs and register
    the convention in `zarr_conventions` (dedup'd by name).
    """
    attrs, version, raw_v3 = load_root_metadata(store)

    registration = {
        "name": CONVENTION_NAME,
        "uuid": CONVENTION_UUID,
        "spec_url": CONVENTION_SPEC_URL,
        "schema_url": CONVENTION_SCHEMA_URL,
    }
    conventions = [c for c in attrs.get("zarr_conventions", [])
                   if c.get("name") != CONVENTION_NAME]
    conventions.append(registration)
    attrs["zarr_conventions"] = conventions
    attrs[CONVENTION_NAME] = list(entries)

    save_root_attrs(store, attrs, version, raw_v3)
