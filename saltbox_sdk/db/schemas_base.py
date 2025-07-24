from typing import Generic, TypeVar

from pydantic import (
    BaseModel,
    Field,
)

from saltbox_sdk.utilities.helpers import Iso8601ZDatetime as TimezoneAwareDatetime

SchemaType = TypeVar('SchemaType', bound=BaseModel)


class CreatedModifiedMixin:
    created: TimezoneAwareDatetime = Field(title='Created')
    modified: TimezoneAwareDatetime = Field(title='Modified')


class PaginatedResponse(BaseModel, Generic[SchemaType]):
    total: int = Field(description='Total number of items', ge=0)
    data: list[SchemaType] = Field(description='Items list')


class CursoredResponse(BaseModel, Generic[SchemaType]):
    next_cursor: int = Field(description='Pointer to get next portion of data, 0 when no more data', ge=0)
    data: list[SchemaType] = Field(description='Items list')


class SkipLimitParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=0, ge=0)
