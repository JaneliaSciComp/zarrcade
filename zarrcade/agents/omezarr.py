import re
import itertools
from typing import Iterator, Any

import zarr
from loguru import logger

from zarrcade.filestore import Filestore
from zarrcade.model import Image, Channel, Axis
from zarrcade.agents import WalkResult

def get(mydict: dict, key: str, default: Any=None):
    if not mydict:
        return default
    return mydict[key] if key in mydict else default


def _yield_color() -> Iterator[str]:
    """ Yield a sequence of colors.
    """
    for c in ['magenta','green','cyan','white','red','green','blue']:
        yield c


def _encode_image(image_group: zarr.Group) -> Image:
    """ Encode an image from an OME-Zarr group.
    """
    if 'multiscales' not in image_group.attrs:
        raise ValueError(f"No multiscales found in group {image_group}")

    multiscales = image_group.attrs['multiscales']
    if len(multiscales) == 0:
        raise ValueError(f"Empty multiscales in group {image_group}")
    if len(multiscales) > 1:
        # Currently, we only support a single multiscale image per group. See here for more info:
        # https://forum.image.sc/t/ome-zarr-storage-structure-for-multiple-multiscale-images/71330
        logger.warning(f"Multiple multiscales found in group {image_group}, using first")

    multiscale = multiscales[0]
    version = get(multiscale, 'version')
    if version != '0.4':
        raise ValueError(f"Unsupported multiscales version {version}")
    
    # Use highest resolution
    fullres = multiscale['datasets'][0]
    fullres_path = fullres['path']

    group_path = image_group.name
    array_path = re.sub('/+', '/', group_path+'/'+fullres_path)

    if array_path not in image_group:
        paths = ', '.join(image_group.keys())
        raise Exception(f"Dataset with path {array_path} does not exist. " +
                        f"Available paths: {paths}")

    array = image_group[array_path]

    scale_transform = next((t for t in fullres['coordinateTransformations'] 
                                       if t['type'] == 'scale'), None)
    if not scale_transform:
        raise ValueError("No scale transformation found in the full scale dataset")
    scales = scale_transform['scale']

    axes_map = {}
    axes_names = []
    dimensions_voxels = []
    voxel_sizes = []
    dimensions = []
    chunks = []
    num_channels = 1
    num_timepoints = 1

    for i, axis in enumerate(multiscale['axes']):
        name = axis['name']
        axes_names.append(name)
        extent = array.shape[i]
        chunk = array.chunks[i]
        scale = scales[i]
        unit = ''
        if axis['type']=='space':
            unit = axis['unit']
            # TODO: add better unit translation support
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

    color_generator = _yield_color()
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
        # If there is no omero metadata, we do the best we can
        for i in range(num_channels):
            name = f"Ch{i}"
            color = next(color_generator)
            channels.append(Channel(name, color))

    return Image(
        group_path = group_path,
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


def _yield_nested_image_groups(z: zarr.Group):
    """ Recursively yield all nested image groups.
    """
    for _,group in z.groups():
        if 'multiscales' in group.attrs:
            yield group
        for nested_group in _yield_nested_image_groups(group):
            yield nested_group


def _yield_image_groups(fs: Filestore, relative_path: str):
    """ Interrogates the OME-Zarr at the given URL and yields all of the images within.
    """
    store = fs.get_store(relative_path)
    z = zarr.open(store, mode='r')
    # Based on https://ngff.openmicroscopy.org/latest/#bf2raw
    if 'bioformats2raw.layout' in z.attrs and z.attrs['bioformats2raw.layout']==3:
        if 'OME' in z:
            # Spec: "series" MUST be a list of string objects,
            # each of which is a path to an image group.
            for s in z['OME'].attrs['series']:
                yield z[s]
        else:
            # Spec: If the "series" attribute does not exist and no "plate" is present:
            # - separate "multiscales" images MUST be stored in consecutively numbered
            #   groups starting from 0 (i.e. "0/", "1/", "2/", "3/", ...).
            for i in itertools.count():
                try:
                    yield z[str(i)]
                except IndexError:
                    break
    elif 'multiscales' in z.attrs:
        # Top level is a single multiscale image
        yield z
    else:
        # Search for multiscales in nested groups
        for group in _yield_nested_image_groups(z):
            yield group


class OmeZarrAgent():
    """ An agent which finds OME-Zarr containers.
        Implements the Agent protocol.
    """

    def walk(self, fs: Filestore, path: str, children: list) -> WalkResult: 
        child_names = [c['name'] for c in children]
        if '.zattrs' in child_names:
            return WalkResult.CONTAINER
        elif '.zarray' in child_names:
            # This is a sign that we have gone too far
            return WalkResult.END
        else:
            return WalkResult.CONTINUE

    
    def yield_images(self, fs: Filestore, path: str, children: list) -> Iterator[Image]:
        absolute_path = fs.get_absolute_path(path)
        logger.trace(f"Reading images in {absolute_path}")

        with logger.catch(message=f"Failed to process {absolute_path}"):
            for image_group in _yield_image_groups(fs, path):
                t = (path, _encode_image(image_group))
                yield t
