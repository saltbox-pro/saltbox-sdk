from fastapi import Request
from fastapi.responses import JSONResponse

from saltbox_sdk.config.logger_config import logger


async def custom_http_handler(_: Request, exc: Exception) -> JSONResponse:
    """Custom exception handler for HTTP exceptions."""
    logger.exception(f'{exc.__class__.__name__}: {getattr(exc, "detail", str(exc))}')
    status_code = 500
    if isinstance(exc, ValueError):
        status_code = getattr(exc, 'status_code', 400)
    return JSONResponse(
        status_code=getattr(exc, 'status_code', status_code),
        content={
            # 'code': getattr(exc, "code", None),
            # 'title': getattr(exc, "title", None),
            'detail': getattr(exc, 'detail', str(exc)),
        },
    )
