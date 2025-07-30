from typing import Annotated

from fastapi import Depends, Header
from redis.asyncio import Redis

from saltbox_sdk.db.redis.config import get_redis
from saltbox_sdk.db.schemas_base import UserShort
from saltbox_sdk.fastapi_utils.errors import UserHeadersMissingError

RedisDependency = Annotated[Redis, Depends(get_redis)]


async def get_current_user(
    x_user_id: str = Header(..., alias='X-User-Id'),
    x_user_email: str = Header(..., alias='X-User-Email'),
    x_user_name: str = Header('', alias='X-User-Name'),
    x_user_email_verified: bool = Header(False, alias='X-User-Email-Verified'),
) -> UserShort:
    if not x_user_id or not x_user_email:
        raise UserHeadersMissingError()
    return UserShort(sub=x_user_id, email=x_user_email, name=x_user_name, email_verified=x_user_email_verified)


def get_redis_dep(redis: RedisDependency) -> Redis:
    return redis
