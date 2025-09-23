from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Channel:
    """ Information about a single channel in the image. 
        Currently loaded from OMERO metadata.
    """
    name: str
    color: str
    pixel_intensity_min: Optional[float] = None
    pixel_intensity_max: Optional[float] = None
    contrast_limit_start: Optional[float] = None
    contrast_limit_end: Optional[float] = None

@dataclass
class Axis:
    """ Information about one axis of the image.
    """
    name: str
    scale: float
    unit: str
    extent: int
    chunk: int

@dataclass
class Image:
    """ Information about an OME-Zarr image.
    """
    group_path: str = None
    num_channels: int = None
    num_timepoints: int = None
    dimensions: str = None
    dimensions_voxels: str = None
    chunk_size: str = None
    voxel_sizes: str = None
    dtype: str = None
    compression: str = None
    channels: list[Channel] = field(default_factory=lambda: [])
    axes: dict[str, Axis] = field(default_factory=lambda: [])
    axes_order: str = None
