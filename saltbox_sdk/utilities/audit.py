import asyncio
from typing import Any

from faststream.rabbit import RabbitBroker

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.event_bus.schemas import (
    AuditCategory,
    AuditEventSchema,
    AuditResourceType,
    AuditSeverity,
    AuditStatus,
    AuditSubjectType,
)
from saltbox_sdk.fastapi_utils.middlewares import AuditRequestContext, get_audit_ctx


class AuditEventPublisher:
    def __init__(self, broker: RabbitBroker, max_concurrent: int):
        self._broker = broker
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.task_group: asyncio.TaskGroup | None = None

    async def start(self) -> None:
        self.task_group = asyncio.TaskGroup()
        await self.task_group.__aenter__()
        logger.info('Audit service started.')

    async def stop(self) -> None:
        if self.task_group is not None:
            logger.info('Stopping audit service, waiting for tasks to complete...')
            await self.task_group.__aexit__(None, None, None)
            self.task_group = None
        logger.info('Audit service stopped.')

    async def publish(self, event: AuditEventSchema) -> None:
        """Publish an audit event asynchronously."""
        if self.task_group is None:
            logger.warning('Audit service is not running. Cannot publish event.')
            return
        self.task_group.create_task(self._publish(event))

    async def _publish(self, event: AuditEventSchema) -> None:
        async with self.semaphore:
            try:
                await self._broker.publish(event, queue='audit_events')
                logger.info('Published audit event: %s', event)
            except Exception as e:
                logger.error('Failed to publish audit event: %s', e)


def build_audit_event(
    *,
    action: str,
    status: AuditStatus,
    resource_path: str,
    category: AuditCategory,
    resource_type: AuditResourceType | str = AuditResourceType.UNKNOWN,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    audit_ctx: AuditRequestContext | None = None,
) -> AuditEventSchema:
    """Build an audit event from the current request context and event details."""
    context = audit_ctx if audit_ctx is not None else get_audit_ctx()
    return AuditEventSchema(
        severity=AuditSeverity.INFO,
        category=category,
        action=action,
        status=status,
        subject_id=context.subject_id if context else None,
        subject_name=context.subject_name if context else None,
        subject_roles=context.subject_roles if context else [],
        subject_type=context.subject_type if context else AuditSubjectType.SYSTEM,
        resource_type=resource_type,
        resource_path=resource_path,
        source_ip=context.source_ip if context else None,
        source_service=context.service if context else 'unknown',
        correlation_id=context.correlation_id if context else None,
        resource_id=resource_id,
        details=details or {},
    )
