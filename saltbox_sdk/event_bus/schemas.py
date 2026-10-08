from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from saltbox_sdk.db.schemas_base import UserShort


class EventBusBaseMessage(BaseModel):
    sender: str
    target: str | None = None
    user: UserShort | None = None


# Minion_extra data


class MinionExtraDataCategoryFieldType(StrEnum):
    STR = 'str'
    INT = 'int'
    FLOAT = 'float'
    BOOL = 'bool'
    LIST = 'list'
    DICT = 'dict'
    BYTES = 'bytes'
    DATETIME = 'datetime'

    @property
    def python_type(self) -> type:
        return _PYTHON_TYPES[self]


_PYTHON_TYPES: dict[MinionExtraDataCategoryFieldType, type] = {
    MinionExtraDataCategoryFieldType.STR: str,
    MinionExtraDataCategoryFieldType.INT: int,
    MinionExtraDataCategoryFieldType.FLOAT: float,
    MinionExtraDataCategoryFieldType.BOOL: bool,
    MinionExtraDataCategoryFieldType.LIST: list,
    MinionExtraDataCategoryFieldType.DICT: dict,
    MinionExtraDataCategoryFieldType.BYTES: bytes,
    MinionExtraDataCategoryFieldType.DATETIME: datetime,
}


class MinionExtraDataCategoryField(BaseModel):
    name: str
    type: MinionExtraDataCategoryFieldType
    is_empty_allowed: bool = Field(default=True)
    is_minion_field: bool = Field(default=False)


class ExtraDataCategoryType(StrEnum):
    STATIC = 'static'
    AGGREGATED = 'aggregated'


class MinionExtraDataExtraFieldsPolicy(StrEnum):
    IGNORE = 'ignore'
    SAVE_TO_CATEGORY = 'save_to_category'
    SAVE_TO_MINION = 'save_to_minion'


class MinionExtraDataCategory(BaseModel):
    source: str
    name: str
    type: ExtraDataCategoryType
    fields: list[MinionExtraDataCategoryField] = Field(default_factory=list)
    extra_fields_policy: MinionExtraDataExtraFieldsPolicy = Field(default=MinionExtraDataExtraFieldsPolicy.IGNORE)
    is_manual_data_allowed: bool | None = Field(default=None)
    title: dict[str, str] | None = Field(default=None)
    description: dict[str, str] | None = Field(default=None)
    icon: str | None = Field(default=None)
    is_single_item: bool = Field(default=False)


class MinionExtraCategoriesSyncMessage(EventBusBaseMessage):
    categories: list[MinionExtraDataCategory] = Field(default_factory=list)


class MinionExtraData(BaseModel):
    category_source: str
    category_name: str
    items: list[dict[str, Any]] = Field(default_factory=list)


class MinionAddOrUpdateExtraDataRequestMessage(EventBusBaseMessage):
    minion_id: str
    master: str

    data_list: list[MinionExtraData]


class MinionRemoveExtraDataRequestMessage(EventBusBaseMessage):
    minion_id: str
    master: str

    category_name: str


# Audit


class AuditCategory(StrEnum):
    AUTHN = 'authentication'
    AUTHZ = 'authorization'
    CONFIG = 'configuration'
    DATA_ACCESS = 'data_access'
    SYSTEM = 'system'
    LIFECYCLE = 'lifecycle'


class AuditResourceType(StrEnum):
    API_ENDPOINTS = 'api_endpoints'
    USERS = 'users'
    MINION = 'minions'
    COLLECTIONS = 'collections'
    POLICIES = 'opa_policies'
    TASKS = 'tasks'
    JOBS = 'jobs'
    EXTRA_DATA = 'extra_data'
    MASTERS = 'masters'
    FILTERS = 'filters'
    PILLARS = 'pillars'
    SALT = 'salt'
    UNKNOWN = 'unknown'


class AuditSubjectType(StrEnum):
    USER = 'user'
    SERVICE = 'service'
    SYSTEM = 'system'


class AuditSeverity(StrEnum):
    INFO = 'info'
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


class AuditStatus(StrEnum):
    SUCCESS = 'success'
    FAILURE = 'failure'
    DENIED = 'denied'
    BLOCKED = 'blocked'


class AuditEventSchema(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    severity: AuditSeverity
    category: AuditCategory
    action: str  # "login", "apply_state", "update_policy", "delete_record"
    status: AuditStatus

    # Subject
    subject_id: str | None = None
    subject_name: str | None = None
    subject_roles: list[str] = Field(default_factory=list)  # был actor_roles
    subject_type: AuditSubjectType | None = None

    # Object
    resource_type: AuditResourceType | str = Field(
        default=AuditResourceType.UNKNOWN,
        description='Type of the resource involved in the event, e.g. "collection", "task", "job"',
    )
    resource_id: str | None = Field(
        default=None,
        description='ID of the resource involved in the event, e.g. mongo document ID, API endpoint, file path',
    )
    resource_path: str | None = Field(
        default=None,
        description='Path of the resource involved in the event, e.g. API endpoint, file path. '
        'More specific than resource_id, used for better SIEM parsing',
    )

    # Context
    source_ip: str | None = Field(default=None, description='Source IP address of the event')
    source_service: str = Field(
        default='unknown',
        description='Name of the service where the event originated, e.g. "core", "gateway", "scheduler"',
    )
    correlation_id: str | None = Field(
        default=None,
        description='Correlation ID for linking related events across services',
    )
    details: dict[str, Any] = Field(default_factory=dict)
    siem_sent: bool = Field(default=False, description='Flag indicating if the event has been sent to SIEM')
