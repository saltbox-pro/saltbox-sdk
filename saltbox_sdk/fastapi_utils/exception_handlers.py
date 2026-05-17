from typing import TYPE_CHECKING, Any

try:
    from bson import ObjectId
except ImportError:
    if TYPE_CHECKING:
        from bson import ObjectId
    else:
        ObjectId = None
from fastapi import Request
from fastapi.responses import JSONResponse

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.exceptions import SaltBoxBaseException


def convert_objectids(obj: Any) -> Any:
    if ObjectId is None:
        return obj
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: convert_objectids(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_objectids(i) for i in obj]
    return obj


async def custom_http_handler(_: Request, exc: Exception) -> JSONResponse:  # noqa: RUF029,RUF100
    """Custom exception handler for HTTP exceptions."""

    extra_fields = {}
    if isinstance(exc, SaltBoxBaseException):
        extra_fields = exc.get_extra_fields()

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

    content = convert_objectids(content)

    return JSONResponse(
        status_code=getattr(exc, 'status_code', status_code),
        content=content,
    )
