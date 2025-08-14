import json
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.redis.config import get_redis
from saltbox_sdk.db.schemas_base import UserShort
from saltbox_sdk.exceptions import UserHeadersMissingException

RedisDependency = Annotated[Redis, Depends(get_redis)]


async def get_current_user(request: Request) -> UserShort:
    x_user_id = request.headers.get('X-User-Id')
    x_user_email = request.headers.get('X-User-Email')
    x_user_name = request.headers.get('X-User-Name', '')
    x_user_email_verified = request.headers.get('X-User-Email-Verified', False)

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


def get_redis_dep(redis: RedisDependency) -> Redis:
    return redis
