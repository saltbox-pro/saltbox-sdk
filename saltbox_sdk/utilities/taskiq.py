from ast import literal_eval
from typing import Any

from redis.asyncio import Redis
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.redis.config import get_redis_now


class TaskAlreadyRunningException(Exception): ...


class UniqueIdMiddleware(TaskiqMiddleware):
    UNIQUE_REDIS_HASH_KEY = 'taskqi_unique_tasks'
    DEFAULT_UNIQUE_LOCK_TIMEOUT = 60

    def __init__(self, rdb: Redis | None = None) -> None:
        if rdb is None:
            self.rdb = get_redis_now()
        else:
            self.rdb = rdb

        super().__init__()

    def get_task_lock_key(
        self, task_name: str, task_unique_kwargs_names: list['str'], task_kwargs: dict[str, Any]
    ) -> str:
        lock_key = f'{task_name}'

        unique_kwargs_values = [str(task_kwargs.get(kwargs_name)) for kwargs_name in task_unique_kwargs_names]

        if unique_kwargs_values:
            lock_key = lock_key + '=' + '__'.join(unique_kwargs_values)

        return lock_key

    async def pre_send(self, message: TaskiqMessage) -> TaskiqMessage:
        task_unique_kwargs_names = literal_eval(message.labels.get('unique_kwargs', '[]'))
        task_unique_lock_timeout = message.labels.get('unique_lock_timeout')

        if task_unique_kwargs_names or task_unique_lock_timeout:
            task_unique_lock_key = self.get_task_lock_key(
                task_name=message.task_name,
                task_unique_kwargs_names=task_unique_kwargs_names,
                task_kwargs=message.kwargs,
            )

            if await self.rdb.hexists(self.UNIQUE_REDIS_HASH_KEY, task_unique_lock_key):
                msg = f'Task "{task_unique_lock_key}" is already running'
                raise TaskAlreadyRunningException(msg)

            async with self.rdb.pipeline() as pipe:
                pipe.hset(self.UNIQUE_REDIS_HASH_KEY, task_unique_lock_key, message.task_id)
                pipe.expire(
                    name=f'{self.UNIQUE_REDIS_HASH_KEY}:{task_unique_lock_key}',
                    time=task_unique_lock_timeout or self.DEFAULT_UNIQUE_LOCK_TIMEOUT,
                )
                await pipe.execute()
        return message

    async def post_execute(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        task_unique_kwargs_names = literal_eval(message.labels.get('unique_kwargs', '[]'))
        task_unique_lock_timeout = message.labels.get('unique_lock_timeout')

        if task_unique_kwargs_names or task_unique_lock_timeout:
            task_unique_lock_key = self.get_task_lock_key(
                task_name=message.task_name,
                task_unique_kwargs_names=task_unique_kwargs_names,
                task_kwargs=message.kwargs,
            )

            await self.rdb.hdel(self.UNIQUE_REDIS_HASH_KEY, task_unique_lock_key)

    async def on_error(self, message: TaskiqMessage, result: TaskiqResult[Any], exception: BaseException) -> None:
        if isinstance(exception, TaskAlreadyRunningException):
            logger.debug(str(exception))
        else:
            super().on_error(message, result, exception)
