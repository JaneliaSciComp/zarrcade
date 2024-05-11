from dataclasses import dataclass
from typing import Optional

from .viewers import viewers

@dataclass
class Channel:
    name: str
    color: str
    pixel_intensity_min: Optional[float] = None
    pixel_intensity_max: Optional[float] = None
    contrast_limit_start: Optional[float] = None
    contrast_limit_end: Optional[float] = None

@dataclass
class Axis:
    name: str
    scale: float
    unit: str
    extent: int
    chunk: int

@dataclass
class Image:
    id: str
    absolute_path: str
    relative_path: str
    thumbnail_path: str
    num_channels: int
    num_timepoints: int
    dimensions: str 
    dimensions_voxels: str
    chunk_size: str
    voxel_sizes: str
    compression: str
    channels: list[Channel]
    axes_order: str
    axes: dict[str, Axis]

    def get_compatible_viewers(self):
        for viewer in viewers:
            yield viewer

@dataclass
class MetadataImage:
    id: str
    image: Image
    metadata: dict[str, str]