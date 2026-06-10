from urllib.parse import unquote
from uuid import uuid4

from pydantic import BaseModel, Field, computed_field, field_serializer

from saltbox_sdk.config.keycloak_config import KC_SETTINGS
from saltbox_sdk.utilities.helpers import Iso8601ZDatetime as TimezoneAwareDatetime


class CreatedModifiedMixin(BaseModel):
    created: TimezoneAwareDatetime = Field(title='Created')
    modified: TimezoneAwareDatetime = Field(title='Modified')


class Source(BaseModel):
    type: str = Field(title='Source type')
    id: str | None = Field(title='Source id', default=None)


class SourceMixin(BaseModel):
    source: Source | None = Field(title='Source', default=None)


class SourceOnlySchema(SourceMixin): ...


class PaginatedResponse[SchemaType: BaseModel | dict](BaseModel):
    total: int = Field(description='Total number of items', ge=0)
    data: list[SchemaType] = Field(description='Items list')


class CursoredResponse[SchemaType: BaseModel](BaseModel):
    next_cursor: int = Field(description='Pointer to get next portion of data, 0 when no more data', ge=0)
    data: list[SchemaType] = Field(description='Items list')


class CursoredTimeseriesResponse[SchemaType: BaseModel](BaseModel):
    next_cursor: TimezoneAwareDatetime | None = Field(
        description='Timestamp of the last item; pass as time_from for the next page. None means no more data.',
        default=None,
    )
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

    @field_serializer('name')
    def serialize_name(self, name: str) -> str:
        return unquote(name)


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


ANONYMOUS_USER_DATA = {
    'sub': 'anonymous',
    'email_verified': False,
    'name': 'Anonymous',
    'email': 'anonymous@localhost',
}


SYSTEM_USER_DATA = {
    'sub': 'system',
    'email_verified': True,
    'name': 'System',
    'email': 'system@localhost',
}


ANONYMOUS_USER = User(**ANONYMOUS_USER_DATA, resource_access=None)
ANONYMOUS_SHORT_USER = UserShort(**ANONYMOUS_USER_DATA)

SYSTEM_USER = User(**SYSTEM_USER_DATA, resource_access=None)  # TODO: check `resource_access`
SYSTEM_SHORT_USER = UserShort(**SYSTEM_USER_DATA)


class AuditContextSchema(BaseModel):
    correlation_id: str
    subject_id: str | None = None
    subject_name: str | None = None
    subject_type: str = 'user'  # user | service | system
    source_ip: str | None = None

    @classmethod
    def new_for_service(cls, service_id: str) -> 'AuditContextSchema':
        """Генерирует контекст для фоновых задач (Scheduler и т.п.)"""
        return cls(
            correlation_id=uuid4().hex,
            subject_id=service_id,
            subject_name=service_id.replace('_', ' ').title(),
            subject_type='service',
            source_ip='internal',
        )

    def to_amqp_headers(self) -> dict[str, str]:
        """Сериализует в AMQP headers (все значения должны быть строками/байтами)"""
        headers = {
            'x-correlation-id': self.correlation_id,
            'x-subject-id': self.subject_id or '',
            'x-subject-name': self.subject_name or '',
            'x-subject-type': self.subject_type,
            'x-source-ip': self.source_ip or 'internal',
        }
        return headers

    @classmethod
    def from_amqp_headers(cls, headers: dict[str, str]) -> 'AuditContextSchema':
        """Восстанавливает контекст из AMQP headers"""
        return cls(
            correlation_id=headers.get('x-correlation-id', uuid4().hex),
            subject_id=headers.get('x-subject-id') or None,
            subject_name=headers.get('x-subject-name') or None,
            subject_type=headers.get('x-subject-type', 'service'),
            source_ip=headers.get('x-source-ip') or None,
        )
