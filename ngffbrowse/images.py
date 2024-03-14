
import os
import sys
sys.path.append(os.getcwd())

import re
import itertools
import zarr
import fsspec
from urllib.parse import urlparse
from pydantic import BaseModel, Field, ConfigDict
from loguru import logger
from ngffbrowse.viewer_config import viewers

class Image(BaseModel):
    model_config = ConfigDict(extra='forbid') 
    id: str = Field(title="Id", description="Id for the data set container (unique within the parent folder)")
    full_path: str = Field(title="Absolute Path", description="Absolute path to the image")
    relative_path: str = Field(title="Relative Path", description="Path to the image, relative to the overall root")
    axes: str = Field(title="Axes", description="String indicating the axes order in the Zarr array (e.g. TCZYX)")
    num_channels: int = Field(title="Num Channels", description="Number of channels in the image")
    num_timepoints: int = Field(title="Num Timepoints", description="Number of timepoints in the image")
    dimensions: str = Field(title="Dimensions", description="Size of the whole data set in nanometers")
    dimensions_voxels: str = Field(title="Dimensions (voxels)", description="Size of the whole data set in voxels")
    chunk_size: str = Field(title="Chunk size", description="Size of Zarr chunks")
    voxel_sizes: str = Field(title="Voxel Size", description="Size of voxels in nanometers. XYZ ordering.")
    compression: str = Field(title="Compression", description="Description of the compression used on the image data")

    def get_url(self):
        """
        """
        return self.full_path

    def get_compatible_viewers(self):
        for viewer in viewers:
            yield viewer


def encode_image(id, full_path, relative_path, image_group):
    multiscales = image_group.attrs['multiscales']
    # TODO: what to do if there are multiple multiscales?
    multiscale = multiscales[0]
    axes = multiscale['axes']

    # Use highest resolution 
    dataset = multiscale['datasets'][0]

    array_path = image_group.name+'/'+dataset['path']
    array_path, _ = re.subn('/+', '/', array_path)

    if array_path not in image_group:
        paths = ', '.join(image_group.keys())
        raise Exception(f"Dataset with path {array_path} does not exist. Available paths: {paths}")

    array = image_group[array_path]
    
    # TODO: shouldn't assume a single transform
    scale = dataset['coordinateTransformations'][0]['scale']

    axes_names = []
    dimensions_voxels = []
    voxel_sizes = []
    dimensions = []
    chunks = []
    num_channels = 1
    num_timepoints = 1
    for i, axis in enumerate(axes):
        axes_names.append(axis['name'].upper())
        unit = ''
        if axis['type']=='space':
            unit = axis['unit']
            if unit in ['micrometer','micron']: unit = " μm"
            if unit=='nanometer': unit = " nm"
            voxel_sizes.append("%.2f%s" % (round(scale[i],2), unit))
            dimensions.append("%.2f%s" % (round(array.shape[i] * scale[i],2), unit))
        elif axis['type']=='channel':
            num_channels = array.shape[i]
            voxel_sizes.append("%i" % scale[i])
            dimensions.append("%i" % (array.shape[i] * scale[i]))
        elif axis['type']=='time':
            num_timepoints = array.shape[i]
            voxel_sizes.append("%i" % scale[i])
            dimensions.append("%i" % (array.shape[i] * scale[i]))
        dimensions_voxels.append(str(array.shape[i]))
        chunks.append("%i" % array.chunks[i])

    return Image(
        id = id,
        full_path = full_path,
        relative_path = relative_path,
        axes = ''.join(axes_names),
        num_channels = num_channels,
        num_timepoints = num_timepoints,
        voxel_sizes = ' ✕ '.join(voxel_sizes),
        dimensions = ' ✕ '.join(dimensions),
        dimensions_voxels = ' ✕ '.join(dimensions_voxels),
        chunk_size = ' ✕ '.join(chunks),
        compression = str(array.compressor)
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
            id = os.path.basename(relative_path)
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
        full_path = base_url + relative_path
        logger.debug(f"Reading images in {full_path}")
        for image in yield_images(full_path, relative_path):
            print(image.__repr__())

