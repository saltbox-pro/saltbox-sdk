import hashlib
import inspect
import json
import random
from ast import literal_eval
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, cast
from uuid import uuid4

from redis.asyncio import Redis
from taskiq import ScheduleSource, TaskiqMessage, TaskiqMiddleware, TaskiqResult
from taskiq.middlewares import SmartRetryMiddleware as OriginalSmartRetryMiddleware

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.redis.config import get_redis_now
from saltbox_sdk.utilities.lua_script import LuaScript
from saltbox_sdk.utilities.taskiq_lock import UniqueTaskLock


class TaskAlreadyRunningException(Exception): ...


class UniqueIdMiddleware(TaskiqMiddleware):
    UNIQUE_REDIS_KEY_PREFIX = 'taskiq:unique'
    DEFAULT_UNIQUE_LOCK_TIMEOUT = 60
    LOCK_KEY_LABEL = '_unique_lock_key'
    OWNER_LABEL = '_unique_lock_owner'
    EXECUTION_OWNER_LABEL = '_unique_execution_owner'
    DEFERRED_LABEL = '_unique_deferred'
    TRANSFER_SCRIPT = LuaScript('utilities/lua/transfer_unique_task.lua')

    def __init__(self, rdb: Redis | None = None) -> None:
        if rdb is None:
            self.rdb = get_redis_now()
        else:
            self.rdb = rdb

        super().__init__()

    def get_task_lock_key(
        self, task_name: str, task_unique_kwargs_names: list[str], task_kwargs: dict[str, Any]
    ) -> str:
        missing = set(task_unique_kwargs_names) - task_kwargs.keys()
        if missing:
            msg = f'Unique task arguments are missing: {sorted(missing)}'
            raise ValueError(msg)
        values = {name: task_kwargs[name] for name in task_unique_kwargs_names}
        payload = json.dumps(values, sort_keys=True, separators=(',', ':'), allow_nan=False)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        return f'{self.UNIQUE_REDIS_KEY_PREFIX}:{task_name}:{digest}'

    def get_task_arguments(self, message: TaskiqMessage) -> dict[str, Any]:
        task = self.broker.find_task(message.task_name) if self.broker is not None else None
        if task is None:
            return message.kwargs
        bound = inspect.signature(task.original_func).bind_partial(*message.args, **message.kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)

    async def pre_send(self, message: TaskiqMessage) -> TaskiqMessage:
        task_unique_kwargs_names = message.labels.get('unique_kwargs', '[]')
        if isinstance(task_unique_kwargs_names, str):
            task_unique_kwargs_names = literal_eval(task_unique_kwargs_names)
        if not isinstance(task_unique_kwargs_names, list) or not all(
            isinstance(name, str) for name in task_unique_kwargs_names
        ):
            msg = 'unique_kwargs must be a list of argument names'
            raise ValueError(msg)
        task_unique_lock_timeout = message.labels.get('unique_lock_timeout')

        if task_unique_kwargs_names or task_unique_lock_timeout is not None:
            timeout = int(
                task_unique_lock_timeout if task_unique_lock_timeout is not None else self.DEFAULT_UNIQUE_LOCK_TIMEOUT
            )
            if timeout <= 0:
                msg = 'unique_lock_timeout must be positive'
                raise ValueError(msg)
            execution_timeout = message.labels.get('unique_execution_lock_timeout')
            if execution_timeout is not None and int(execution_timeout) <= 0:
                msg = 'unique_execution_lock_timeout must be positive'
                raise ValueError(msg)
            task_unique_lock_key = self.get_task_lock_key(
                task_name=message.task_name,
                task_unique_kwargs_names=task_unique_kwargs_names,
                task_kwargs=self.get_task_arguments(message) if task_unique_kwargs_names else {},
            )
            token = uuid4().hex
            acquired = False
            previous_token = message.labels.get(self.OWNER_LABEL)
            execution_retry = (
                previous_token
                and message.labels.get(self.LOCK_KEY_LABEL) == task_unique_lock_key
                and message.labels.get(self.EXECUTION_OWNER_LABEL)
                and int(message.labels.get('_retries', 0)) > 0
            )
            if previous_token and message.labels.get(self.LOCK_KEY_LABEL) == task_unique_lock_key:
                evaluate = cast(Callable[..., Awaitable[int]], self.rdb.eval)
                acquired = bool(
                    await evaluate(
                        self.TRANSFER_SCRIPT.content, 1, task_unique_lock_key, previous_token, token, timeout
                    )
                )
            if not acquired:
                acquired = bool(await self.rdb.set(task_unique_lock_key, token, nx=True, ex=timeout))
            if not acquired and not execution_retry:
                msg = f'Task "{task_unique_lock_key}" is already running'
                raise TaskAlreadyRunningException(msg)
            message.labels[self.LOCK_KEY_LABEL] = task_unique_lock_key
            message.labels[self.OWNER_LABEL] = token
            message.labels.pop(self.EXECUTION_OWNER_LABEL, None)
            message.labels.pop(self.DEFERRED_LABEL, None)
        return message

    def get_lock(self, message: TaskiqMessage) -> UniqueTaskLock | None:
        key = message.labels.get(self.LOCK_KEY_LABEL)
        token = message.labels.get(self.OWNER_LABEL)
        if key and token:
            return UniqueTaskLock(
                rdb=self.rdb,
                enqueue_key=key,
                enqueue_owner=token,
                execution_owner=message.labels.get(self.EXECUTION_OWNER_LABEL, ''),
                lock_timeout=int(message.labels.get('unique_lock_timeout', self.DEFAULT_UNIQUE_LOCK_TIMEOUT)),
                execution_lock_timeout=(
                    int(message.labels['unique_execution_lock_timeout'])
                    if message.labels.get('unique_execution_lock_timeout') is not None else None
                ),
            )
        return None

    async def acquire_execution(self, message: TaskiqMessage) -> bool:
        message.labels[self.EXECUTION_OWNER_LABEL] = uuid4().hex
        lock = self.get_lock(message)
        if lock is None:
            message.labels.pop(self.EXECUTION_OWNER_LABEL, None)
            return True
        acquired = await lock.acquire_execution()
        if not acquired:
            message.labels.pop(self.EXECUTION_OWNER_LABEL, None)
        return acquired

    async def post_execute(self, message: TaskiqMessage, result: TaskiqResult[Any]) -> None:
        if message.labels.get(self.DEFERRED_LABEL):
            return
        lock = self.get_lock(message)
        if lock is not None:
            await lock.release_all_locks()

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
