from fastapi import Request
from fastapi.responses import JSONResponse

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.exceptions import SaltBoxBaseException


async def custom_http_handler(_: Request, exc: Exception) -> JSONResponse:  # noqa: RUF029,RUF100
    """Custom exception handler for HTTP exceptions."""

    extra_fields = {}
    if isinstance(exc, SaltBoxBaseException):
        extra_fields = {attr: getattr(exc, attr, '** MISSING VALUE **') for attr in exc.extra_fields}

    exc_type_str = exc.__class__.__name__
    logger.exception('%s: %s', exc_type_str, getattr(exc, 'detail', str(exc)))
    for attr, val in extra_fields.items():
        logger.error('%s.%s = %s', exc_type_str, attr, val)

    status_code = 500
    if isinstance(exc, ValueError):
        status_code = getattr(exc, 'status_code', 400)

    content = {
        **extra_fields,
        'detail': getattr(exc, 'detail', str(exc)),
    }

    return JSONResponse(
        status_code=getattr(exc, 'status_code', status_code),
        content=content,
    )
