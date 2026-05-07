import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from urllib.parse import unquote
from uuid import uuid4

from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.event_bus.schemas import AuditSubjectType

RequestResponseEndpoint = Callable[[Request], Awaitable[Response]]


class UserContextSchema(BaseModel):
    subject_id: str | None
    subject_name: str | None
    subject_roles: list[str]
    subject_type: AuditSubjectType | None
    source_ip: str | None


class AuditRequestContext(UserContextSchema):
    correlation_id: str | None
    service: str


_audit_ctx: ContextVar[AuditRequestContext | None] = ContextVar('audit_ctx', default=None)


def get_audit_ctx() -> AuditRequestContext | None:
    return _audit_ctx.get()


class AuditContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        service: str,
        gen_cor_id_if_missing: bool = False,
        add_to_response: bool = False,
    ) -> None:
        super().__init__(app)
        self.service = service
        self.gen_cor_id_if_missing = gen_cor_id_if_missing
        self.add_to_response = add_to_response

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        logger.debug('Processing request in AuditContextMiddleware')
        correlation_id = self._get_or_generate_correlation_id(request)

        audit_ctx = AuditRequestContext(
            correlation_id=correlation_id,
            service=self.service,
            **self._get_user_info(request).model_dump(),
        )
        token = _audit_ctx.set(audit_ctx)
        try:
            response = await call_next(request)
            response_correlation_id = response.headers.get('X-Request-ID')
            if correlation_id != response_correlation_id:
                logger.warning(
                    f'Corr ID in response ({response_correlation_id}) does not match request context ({correlation_id})'
                )
            else:
                logger.info('Correlation ID in response matches request context')
        finally:
            _audit_ctx.reset(token)

        if self.add_to_response and correlation_id:
            response.headers['X-Request-ID'] = correlation_id

        return response

    def _get_user_info(self, request: Request) -> UserContextSchema:
        user = getattr(request.state, 'user', None)
        if not user:
            logger.debug('No user info found in request.state.user; falling back to headers')
        source_ip = request.headers.get('X-Real-IP')

        subject_roles = getattr(user, 'roles', None)
        if subject_roles is None:
            raw_roles = request.headers.get('X-User-Roles', '')
            subject_roles = [r.strip() for r in raw_roles.split(',') if r.strip()]
        elif isinstance(subject_roles, str):
            subject_roles = [r.strip() for r in subject_roles.split(',') if r.strip()]

        return UserContextSchema(
            subject_id=getattr(user, 'sub', request.headers.get('X-User-Id')),
            subject_name=getattr(user, 'name', unquote(request.headers.get('X-User-Name', ''))),
            subject_roles=subject_roles,
            subject_type=AuditSubjectType.USER,  # TODO: determine subject type based on auth method or other info
            source_ip=source_ip,
        )

    def _get_or_generate_correlation_id(self, request: Request) -> str | None:
        correlation_id = request.headers.get('X-Request-ID')

        if correlation_id and (('\n' in correlation_id) or ('\r' in correlation_id) or (len(correlation_id) > 200)):
            logger.warning('Invalid correlation ID in request headers; ignoring')
            correlation_id = None

        if not correlation_id and self.gen_cor_id_if_missing:
            correlation_id = str(uuid4())
            logger.debug(f'Generated new correlation ID: {correlation_id}')

        return correlation_id


class ServerTimingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, service: str) -> None:
        super().__init__(app)
        self.service = service

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000
        metric = f'{self.service};dur={duration_ms:.2f}'
        if existing := response.headers.get('Server-Timing'):
            response.headers['Server-Timing'] = f'{existing}, {metric}'
        else:
            response.headers['Server-Timing'] = metric
        return response
