from pydantic import (
    BaseModel,
    Field,
)

from saltbox_sdk.utilities.helpers import Iso8601ZDatetime as TimezoneAwareDatetime


class CreatedModifiedMixin:
    created: TimezoneAwareDatetime = Field(title='Created')
    modified: TimezoneAwareDatetime = Field(title='Modified')


class PaginatedResponse[SchemaType: BaseModel](BaseModel):
    total: int = Field(description='Total number of items', ge=0)
    data: list[SchemaType] = Field(description='Items list')


class CursoredResponse[SchemaType: BaseModel](BaseModel):
    next_cursor: int = Field(description='Pointer to get next portion of data, 0 when no more data', ge=0)
    data: list[SchemaType] = Field(description='Items list')


class SkipLimitParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=0, ge=0)
