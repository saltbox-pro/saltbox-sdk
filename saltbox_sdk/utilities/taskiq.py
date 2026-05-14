import random
from ast import literal_eval
from collections.abc import Iterable
from typing import Any

from redis.asyncio import Redis
from taskiq import ScheduleSource, TaskiqMessage, TaskiqMiddleware, TaskiqResult
from taskiq.middlewares import SmartRetryMiddleware as OriginalSmartRetryMiddleware

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


class SmartRetryMiddleware(OriginalSmartRetryMiddleware):
    def __init__(
        self,
        delay_label_name: str = 'retry_delay',
        default_retry_count: int = 3,
        default_retry_label: bool = False,
        no_result_on_retry: bool = True,
        default_delay: float = 5,
        use_jitter: bool = False,
        use_delay_exponent: bool = False,
        max_delay_exponent: float = 60,
        schedule_source: ScheduleSource | None = None,
        types_of_exceptions: Iterable[type[BaseException]] | None = None,
    ) -> None:
        super().__init__(
            default_retry_count=default_retry_count,
            default_retry_label=default_retry_label,
            no_result_on_retry=no_result_on_retry,
            default_delay=default_delay,
            use_jitter=use_jitter,
            use_delay_exponent=use_delay_exponent,
            max_delay_exponent=max_delay_exponent,
            schedule_source=schedule_source,
            types_of_exceptions=types_of_exceptions,
        )
        self.delay_label_name = delay_label_name

    def make_delay(self, message: TaskiqMessage, retries: int) -> float:
        """
        Calculate retry delay.

        Includes jitter and exponential backoff if enabled.

        :param message: Task message.
        :param retries: Current retry count.
        :return: Delay in seconds.
        """
        delay = float(message.labels.get(self.delay_label_name, self.default_delay))
        if self.use_delay_exponent:
            delay = min(delay * retries, self.max_delay_exponent)

        if self.use_jitter:
            delay += random.random()  # noqa: S311

        return delay
