import sys
from pathlib import Path
from enum import Enum
from typing import List, Set, Dict
from functools import cache

from loguru import logger
from pydantic import AnyUrl, HttpUrl, BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource
)

class Database(BaseModel):
    """ Database settings """
    url: AnyUrl = 'sqlite:///database.db'
    debug_sql: bool = False


class FileProxy(BaseModel):
    """ File proxy settings """
    collection: str
    url: HttpUrl


class DataType(str, Enum):
    """ Possible filter data types """
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


class Settings(BaseSettings):
    """ Zarrcade settings can be read from a settings.yaml file, 
        or from the environment, with environment variables prepended 
        with "zarrcade_" (case insensitive). The environment variables can
        be passed in the environment or in a .env file. 
    """

    log_level: str = 'INFO'
    base_url: HttpUrl = 'http://127.0.0.1:8000/'
    database: Database = Database()
    proxies: List[FileProxy] = []
    exclude_paths: List[str] = []
    filters: List[Filter] = []
    title_column_name: str = None
    hide_columns: Set[str] = set()

    model_config = SettingsConfigDict(
        yaml_file="settings.yaml",
        env_file='.env',
        env_prefix='zarrcade_',
        env_nested_delimiter="__",
        env_file_encoding='utf-8'
    )

    @classmethod
    def settings_customise_sources(  # noqa: PLR0913
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@cache
def get_settings():

    # Read settings
    settings = Settings()
    
    # Configure logging
    logger.remove()
    logger.add(sys.stdout, level=settings.log_level)
    
    return settings
