import logging
from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from saltbox_sdk.config.redis_config import REDIS_SETTINGS

LOGGER = logging.getLogger(__name__)


def _make_pool() -> ConnectionPool:
    return ConnectionPool.from_url(REDIS_SETTINGS.redis_url, **REDIS_SETTINGS.redis_connection_kwargs)


POOL = _make_pool()


def get_redis_now() -> Redis:
    return Redis(connection_pool=POOL)


async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis(connection_pool=POOL)
    yield redis
    LOGGER.debug('Close redis connection now')
    await redis.aclose()  # type: ignore[attr-defined]
