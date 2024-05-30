from typing import Any, Callable, Set, Union

from pydantic import (
    BaseModel,
    Field,
    AnyUrl,
    HttpUrl
)

from pathlib import Path
from pydantic import BaseModel, ValidationError, field_validator
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import DirectoryPath, Field, FilePath, ValidationError, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource



class Settings(BaseSettings):

    base_url: HttpUrl = 'http://127.0.0.1:8000/'
    data_url: Union[AnyUrl | Path] = None
    db_url: AnyUrl = 'sqlite:///:memory:'

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

    @field_validator('data_url')
    def must_define(cls, v): # pylint: disable=no-self-argument
        if not v:
            raise ValueError('You must define a the data_url setting '+
                '(or ZARRCADE_DATA_URL environment variable) '+
                'pointing to a location where OME-Zarr images are found.')
        return v
