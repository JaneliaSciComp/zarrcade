from dataclasses import dataclass
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
    relative_path: str
    zarr_path: str
    group_path: str
    num_channels: int
    num_timepoints: int
    dimensions: str
    dimensions_voxels: str
    chunk_size: str
    voxel_sizes: str
    compression: str
    channels: list[Channel]
    axes: dict[str, Axis]
    axes_order: str

    def get_compatible_viewers(self):
        for viewer in viewers:
            yield viewer

    def get_id(self):
        return self.relative_path
    
    def get_title(self):
        return self.relative_path


@dataclass
class MetadataImage:
    """ Additional metadata about an OME-Zarr image that is 
        provided outside of the zarr container.
    """
    id: str
    image: Image
    aux_image_path: str
    thumbnail_path: str
    metadata: dict[str, str]
    