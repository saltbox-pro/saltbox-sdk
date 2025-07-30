from pydantic import BaseModel, Field, computed_field

from saltbox_sdk.config.keycloak_config import KC_SETTINGS
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


class AccessModel(BaseModel):
    roles: list[str] = Field(default=[])


class UserShort(BaseModel):
    sub: str = Field(title='User ID')
    email: str = Field(title='User email', default='anonymous@localhost')
    email_verified: bool = Field(title='Is email verified', default=False)
    name: str = Field(title='User name', default='Anonymous')


class User(UserShort):
    resource_access: dict[str, AccessModel] | None = Field(default=None, exclude=True)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def roles(self) -> list[str]:
        client_roles: list[str] = []
        if self.resource_access:
            try:
                client_roles = self.resource_access[KC_SETTINGS.client].roles
            except KeyError:
                pass

        return client_roles


ANONYMOUS_USER = User(
    sub='anonymous',
    resource_access=None,
    email_verified=False,
    name='Anonymous',
    email='anonymous@localhost',
)
