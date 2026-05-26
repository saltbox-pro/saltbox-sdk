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


class MinionAddOrUpdateExtraDataRequestMessage(EventBusBaseMessage):
    minion_id: str
    master: str

    category_name: str
    values: list[Any]


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
    API_ENDPOINT = 'api_endpoint'
    USER = 'user'
    MINION = 'minion'
    COLLECTION = 'collection'
    POLICY = 'opa_policy'
    TASK = 'task'
    JOB = 'job'
    SCHEDULE = 'schedule'
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
    resource_type: AuditResourceType = Field(
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
