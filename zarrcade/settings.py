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

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='zarrcade_')

    base_url: HttpUrl = 'http://127.0.0.1:8000/'
    data_url: Union[AnyUrl | Path] = None
    db_url: AnyUrl = 'sqlite:///:memory:'

    @field_validator('data_url')
    def must_define(cls, v): # pylint: disable=no-self-argument
        if not v:
            raise ValueError('You must define a the data_url setting '+
                '(or ZARRCADE_DATA_URL environment variable) '+
                'pointing to a location where OME-Zarr images are found.')
        return v
