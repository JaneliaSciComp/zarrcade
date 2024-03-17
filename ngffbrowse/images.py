
import os
import sys
sys.path.append(os.getcwd())

import re
import itertools
import zarr
import fsspec
from dataclasses import dataclass
from typing import Optional

from urllib.parse import urlparse
from loguru import logger

from .viewers import viewers

def get(dict, key, default=None):
    if not dict: return default
    return dict[key] if key in dict else default

    
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


def encode_image(id, absolute_path, relative_path, image_group):
    multiscales = image_group.attrs['multiscales']
    # TODO: what to do if there are multiple multiscales?
    multiscale = multiscales[0]
    axes = multiscale['axes']

    # Use highest resolution 
    fullres_dataset = multiscale['datasets'][0]
    fullres_path = fullres_dataset['path']

    array_path = image_group.name+'/'+fullres_dataset['path']
    array_path, _ = re.subn('/+', '/', array_path)

    if array_path not in image_group:
        paths = ', '.join(image_group.keys())
        raise Exception(f"Dataset with path {array_path} does not exist. Available paths: {paths}")

    array = image_group[array_path]
    
    # TODO: shouldn't assume a single transform
    scales = fullres_dataset['coordinateTransformations'][0]['scale']

    axes_map = {}
    axes_names = []
    dimensions_voxels = []
    voxel_sizes = []
    dimensions = []
    chunks = []
    num_channels = 1
    num_timepoints = 1
    for i, axis in enumerate(axes):
        name = axis['name']
        axes_names.append(name)
        extent = array.shape[i]
        chunk = array.chunks[i]
        scale = scales[i]
        unit = ''
        if axis['type']=='space':
            unit = axis['unit']
            # TODO: better unit translation support
            if unit in ['micrometer','micron']: unit = 'um'
            if unit=='nanometer': unit = 'nm'

            print_unit = unit
            if unit == 'um': print_unit = "μm"

            voxel_sizes.append("%.2f %s" % (round(scale,2), print_unit))
            dimensions.append("%.2f %s" % (round(extent * scale,2), print_unit))
        elif axis['type']=='channel':
            num_channels = extent
            voxel_sizes.append("%i" % scale)
            dimensions.append("%i" % (extent * scale))
        elif axis['type']=='time':
            num_timepoints = extent
            voxel_sizes.append("%i" % scale)
            dimensions.append("%i" % (extent * scale))
        dimensions_voxels.append(str(extent))
        chunks.append("%i" % chunk)
        axes_map[name] = Axis(name, scale, unit, extent, chunk)

    def yield_color():
        for c in ['magenta','green','cyan','white','red','green','blue']:
            yield c

    color_generator = yield_color()

    channels = []
    if 'omero' in image_group.attrs and 'channels' in image_group.attrs['omero']:
        for i, channel_meta in enumerate(image_group.attrs['omero']['channels']):
            window = channel_meta['window']
            channels.append(Channel(
                name = get(channel_meta, 'label', f"Ch{i}"),
                color = get(channel_meta, 'color', next(color_generator)),
                pixel_intensity_min = get(window, 'min'),
                pixel_intensity_max = get(window, 'max'),
                contrast_limit_start = get(window, 'start'),
                contrast_limit_end = get(window, 'end')
            ))
    else:
        for i in range(num_channels):
            name = f"Ch{i}"
            color = next(color_generator)
            channels.append(Channel(name, color))

    thumbnail_path = None
    if 'janelia' in image_group.attrs:
        janelia = image_group.attrs['janelia']
        if 'projections' in janelia:
            projections = janelia['projections']
            if fullres_path in projections:
                fullres_projections = projections[fullres_path]
                thumbnail_path = fullres_projections['xy']

    return Image(
        id = id,
        absolute_path = absolute_path,
        relative_path = relative_path,
        thumbnail_path = thumbnail_path,
        num_channels = num_channels,
        num_timepoints = num_timepoints,
        voxel_sizes = ' ✕ '.join(voxel_sizes),
        dimensions = ' ✕ '.join(dimensions),
        dimensions_voxels = ' ✕ '.join(dimensions_voxels),
        chunk_size = ' ✕ '.join(chunks),
        compression = str(array.compressor),
        channels = channels,
        axes_order = ''.join(axes_names),
        axes = axes_map
    )
    

def yield_nested_image_groups(z):
    for _,group in z.groups():
        if 'multiscales' in group.attrs:
            yield group
        for image in yield_nested_image_groups(group):
            yield image


def yield_image_groups(url):
    ''' Interrogates the OME-Zarr at the given URL and yields all of the 2-5D images within.
    '''
    z = zarr.open(url, mode='r')
    # Based on https://ngff.openmicroscopy.org/latest/#bf2raw
    if 'bioformats2raw.layout' in z.attrs and z.attrs['bioformats2raw.layout']==3:
        if 'OME' in z:
            series = z['OME'].attrs['series']
            if len(series) == 1:
                # We treat this as a single image for easier consumption
                yield z[series[0]]
            else:
                # Spec: "series" MUST be a list of string objects, each of which is a path to an image group.
                for image_id in series:
                    yield z[image_id]
        else:
            # Spec: If the "series" attribute does not exist and no "plate" is present:
            # - separate "multiscales" images MUST be stored in consecutively numbered groups starting from 0 (i.e. "0/", "1/", "2/", "3/", ...).
            for i in itertools.count():
                try:
                    yield z[str(i)]
                except:
                    break
    elif 'multiscales' in z.attrs:
        yield z
    else:
        for image in yield_nested_image_groups(z):
            yield image


def yield_images(absolute_path, relative_path):
    with logger.catch(message=f"Failed to process {absolute_path}"):
        for image_group in yield_image_groups(absolute_path):
            group_abspath = absolute_path
            group_relpath = relative_path
            id = relative_path
            if image_group.path:
                gp = '/'+image_group.path
                id += gp
                group_abspath += gp
                group_relpath += gp
            yield encode_image(id, group_abspath, group_relpath, image_group)


def get_fs(url):
    pu = urlparse(url)
    if pu.scheme in ['http','https'] and pu.netloc.endswith('.s3.amazonaws.com'):
        # Convert S3 HTTP URLs (which do not support list operations) back to S3 REST API
        fs = fsspec.filesystem('s3')
        p = pu.netloc.split('.')[0] + pu.path
    else:
        fs = fsspec.filesystem(pu.scheme)
        p = pu.netloc + pu.path
        if isinstance(fs,fsspec.implementations.local.LocalFileSystem):
            # Normalize the path
            p = os.path.abspath(p)
    return fs, p


def _yield_ome_zarrs(fs, root, path, depth=0, maxdepth=10):
    if depth>maxdepth: return
    logger.trace("ls "+path)
    children = fs.ls(path, detail=True)
    child_names = [os.path.basename(c['name']) for c in children]
    if '.zattrs' in child_names:
        yield path
    elif '.zarray' in child_names:
        # This is a sign that we have gone too far 
        pass
    else:
        # drill down until we find a zarr
        for d in [i['name'] for i in children if i['type']=='directory']:
            dname = os.path.basename(d)
            if dname.endswith('.n5') or dname.endswith('align') or dname.startswith('mag') \
                    or dname in ['raw', 'align', 'dat', 'tiles_destreak', 'mag1']: 
                continue
            logger.trace(f"Searching {d}")
            for zarr_path in _yield_ome_zarrs(fs, root, d, depth+1):
                yield zarr_path


def yield_ome_zarrs(fs, root):
    for zarr_path in _yield_ome_zarrs(fs, root, root):
        yield zarr_path

if __name__ == '__main__':
    base_url = sys.argv[1]
    fs, fsroot = get_fs(base_url)
    logger.debug(f"Root is {fsroot}")
    for zarr_path in yield_ome_zarrs(fs, fsroot):
        logger.debug(f"Found images in {zarr_path}")
        relative_path = zarr_path.removeprefix(fsroot)
        absolute_path = base_url + relative_path
        logger.debug(f"Reading images in {absolute_path}")
        for image in yield_images(absolute_path, relative_path):
            print(image.__repr__())

