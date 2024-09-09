import os
import re
import itertools

import zarr
import pathspec 
from loguru import logger

from zarrcade.model import Image, Channel, Axis

def get(mydict, key, default=None):
    if not mydict:
        return default
    return mydict[key] if key in mydict else default


def encode_image(zarr_path, image_group):
    multiscales = image_group.attrs['multiscales']
    # TODO: what to do if there are multiple multiscales?
    multiscale = multiscales[0]
    axes = multiscale['axes']

    # Use highest resolution
    fullres_dataset = multiscale['datasets'][0]
    fullres_path = fullres_dataset['path']

    group_path = image_group.name
    array_path = group_path+'/'+fullres_dataset['path']
    array_path, _ = re.subn('/+', '/', array_path)

    if array_path not in image_group:
        paths = ', '.join(image_group.keys())
        raise Exception(f"Dataset with path {array_path} does not exist. " +
                         f"Available paths: {paths}")

    array = image_group[array_path]

    # TODO: we shouldn't assume a single transform
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

    return Image(
        relative_path = zarr_path + group_path,
        zarr_path = zarr_path,
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


def yield_nested_image_groups(z):
    for _,group in z.groups():
        if 'multiscales' in group.attrs:
            yield group
        for nested_group in yield_nested_image_groups(group):
            yield nested_group


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
                # Spec: "series" MUST be a list of string objects,
                # each of which is a path to an image group.
                for image_id in series:
                    yield z[image_id]
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
        yield z
    else:
        for group in yield_nested_image_groups(z):
            yield group


# TODO: should work on a Filesystem and relative path
def yield_images(absolute_path, relative_path):
    logger.trace(f"absolute_path: {absolute_path}")
    logger.trace(f"relative_path: {relative_path}")
    with logger.catch(message=f"Failed to process {absolute_path}"):
        for image_group in yield_image_groups(absolute_path):
            group_abspath = absolute_path
            group_relpath = relative_path
            image_id = relative_path
            if image_group.path:
                gp = '/'+image_group.path
                image_id += gp
                group_abspath += gp
                group_relpath += gp
            yield encode_image(relative_path, image_group)


def _yield_ome_zarrs(fs, path, depth=0, maxdepth=10):
    if depth>maxdepth: return

    for exclude_path in fs.exclude_paths:
        spec = pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, exclude_path.splitlines())
        if spec.match_file(path):
            logger.trace(f"excluding {path}")
            return

    logger.trace(f"listing {path}")
    children = fs.get_children(path)
    
    logger.debug(f"Searching for zarrs in {path}")    
    child_names = [c['name'] for c in children]
    if '.zattrs' in child_names:
        yield path
    elif '.zarray' in child_names:
        # This is a sign that we have gone too far
        pass
    else:
        # drill down until we find a zarr
        for d in [c['path'] for c in children if c['type']=='directory']:
            for zarr_path in _yield_ome_zarrs(fs, d, depth+1):
                yield zarr_path


def yield_ome_zarrs(fs):
    for zarr_path in _yield_ome_zarrs(fs, ''):
        yield zarr_path
