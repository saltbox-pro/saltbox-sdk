from redis.asyncio import Redis

from saltbox_sdk.db.redis.config import get_redis_now


class MigrationRedisMixin:
    _redis_client: Redis | None = None

    def redis_client(self) -> Redis:
        if self._redis_client is None:
            self._redis_client = get_redis_now()

        return self._redis_client
