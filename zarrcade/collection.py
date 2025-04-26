import yaml
from enum import Enum
from typing import Dict, List, Set

from pydantic import BaseModel, AnyUrl, HttpUrl
from pydantic.types import Path
from pydantic_settings import BaseSettings


class DataType(str, Enum):
    """ Possible ways that the data can be interpreted for filtering"""
    string = 'string'
    csv = 'csv'


class FilterType(str, Enum):
    """ Possible filter widget types """
    dropdown = 'dropdown'


class Filter(BaseModel):
    """ Filter settings """
    db_name: str = None
    column_name: str
    data_type: DataType = DataType.string
    filter_type: FilterType = FilterType.dropdown
    _values: Dict[str,str] = {}


class AuxImageMode(str, Enum):
    """ How to find auxiliary images """
    
    absolute = 'absolute'
    """ Use an absolute URL to the auxiliary image """

    relative = 'relative'
    """ Use the filestore to find auxiliary images, with paths relative to the data URL """

    local = 'local'
    """ Use the local filesystem to find auxiliary images """


class DiscoverySettings(BaseModel):
    """ Settings for how to discover images within a common data URL. """

    data_url: AnyUrl | Path | None = None
    """ The URL to the images. May be None if full image paths are provided in the metadata file. """

    exclude_paths: List[str] = ['**/.zarrcade']
    """ Paths to exclude when discovering images in the data URL. Supports git-style wildcards like **/*.tiff"""

    proxy_url: HttpUrl | None = None
    """ The URL of the proxy server. If provided, the relative image paths will be fetched 
    via the proxy server. This setting is only used if the data_url is provided. """


class CollectionSettings(BaseSettings):
    """ Configuration for an image collection """

    label: str
    """ The label shown in the UI for the collection. """

    discovery: DiscoverySettings | None = None
    """ Settings for how to discover images within a common data URL. """

    metadata_file: str | None = None
    """ The path to the metadata file used during the loading process. """

    aux_image_mode: AuxImageMode = AuxImageMode.local
    """ How to find auxiliary images (thumbnails, etc.) """

    title_column_name: str | None = None
    """ The name of the column that contains the title of the image. """

    filters: List[Filter] = []
    """ The data filters to show in the UI """

    hide_columns: Set[str] = set()
    """ The columns to hide from the UI """


def load_collection_settings(settings_file: str) -> CollectionSettings:
    """ Load the collection settings from a file """
    with open(settings_file) as f:
        settings_dict = yaml.safe_load(f)
    return CollectionSettings.model_validate(settings_dict)


if __name__ == "__main__":
    import sys
    import pprint
    settings = load_collection_settings(sys.argv[1])
    pprint.pprint(settings.model_dump())
