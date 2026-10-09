import json
from urllib.parse import unquote

from fastapi import Request

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.schemas_base import UserShort
from saltbox_sdk.exceptions import UserHeadersMissingException
from saltbox_sdk.utilities.audit import AuditEventPublisher


async def get_current_user(request: Request) -> UserShort:
    x_user_id = request.headers.get('X-User-Id')
    x_user_email = request.headers.get('X-User-Email')
    x_user_name = unquote(request.headers.get('X-User-Name', ''))
    x_user_email_verified = request.headers.get('X-User-Email-Verified', '').lower() == 'true'

    if not x_user_id or not x_user_email:
        raise UserHeadersMissingException()
    return UserShort(
        sub=x_user_id,
        email=x_user_email,
        name=x_user_name,
        email_verified=x_user_email_verified,
    )


async def get_opa_query(request: Request) -> dict:
    query_str = request.query_params.get('opa_query', None)
    query = json.loads(query_str) if query_str else {}
    logger.info(f'OPA query: {query}')
    return query


async def get_audit_publisher(request: Request) -> AuditEventPublisher | None:
    if not hasattr(request.app.state, 'audit_publisher'):
        logger.error('Audit service is not initialized.')
        return None
    audit_publisher: AuditEventPublisher = request.app.state.audit_publisher
    return audit_publisher
