from dataclasses import dataclass, field
from typing import Optional

from .viewers import viewers

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
    relative_path: str = None
    zarr_path: str = None
    group_path: str = None
    num_channels: int = None
    num_timepoints: int = None
    dimensions: str = None
    dimensions_voxels: str = None
    chunk_size: str = None
    voxel_sizes: str = None
    compression: str = None
    channels: list[Channel] = field(default_factory=lambda: [])
    axes: dict[str, Axis] = field(default_factory=lambda: [])
    axes_order: str = None

    def get_compatible_viewers(self):
        for viewer in viewers:
            yield viewer

    def get_id(self):
        return self.relative_path
    


@dataclass
class MetadataImage:
    """ Additional metadata about an OME-Zarr image that is 
        provided outside of the zarr container.
    """
    id: str
    collection: str
    image: Image
    aux_image_path: str
    thumbnail_path: str
    metadata: dict[str, str]
    