from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import cast

from redis.asyncio import Redis

from saltbox_sdk.utilities.lua_script import LuaScript

_RELEASE_SCRIPT = LuaScript('utilities/lua/release_unique_task.lua')
_RELEASE_ALL_SCRIPT = LuaScript('utilities/lua/release_unique_task_locks.lua')
_ACQUIRE_SCRIPT = LuaScript('utilities/lua/acquire_unique_task_execution.lua')


@dataclass(frozen=True)
class UniqueTaskLock:
    rdb: Redis
    enqueue_key: str
    enqueue_owner: str
    execution_owner: str = ''
    lock_timeout: int = 60
    execution_lock_timeout: int | None = None

    def __post_init__(self) -> None:
        if self.lock_timeout <= 0 or (
            self.execution_lock_timeout is not None and self.execution_lock_timeout <= 0
        ):
            msg = 'Unique task lock timeouts must be positive'
            raise ValueError(msg)

    @property
    def execution_key(self) -> str:
        return f'{self.enqueue_key}:execution'

    async def acquire_execution(self) -> bool:
        """Try once; a busy task must be deferred by the broker."""
        if not self.execution_owner:
            msg = 'An execution owner is required to acquire the execution lock'
            raise ValueError(msg)
        evaluate = cast(Callable[..., Awaitable[int]], self.rdb.eval)
        return bool(
            await evaluate(
                _ACQUIRE_SCRIPT.content,
                2,
                self.enqueue_key,
                self.execution_key,
                self.enqueue_owner,
                self.execution_owner,
                self.lock_timeout * 1000,
                (self.execution_lock_timeout or 0) * 1000,
            )
        )

    async def release_enqueue_lock(self) -> None:
        """Allow a successor to be queued, retaining exclusive execution."""
        evaluate = cast(Callable[..., Awaitable[int]], self.rdb.eval)
        await evaluate(_RELEASE_SCRIPT.content, 1, self.enqueue_key, self.enqueue_owner)

    async def release_all_locks(self) -> None:
        """Release only this invocation's locks, allowing a successor to execute."""
        evaluate = cast(Callable[..., Awaitable[int]], self.rdb.eval)
        await evaluate(
            _RELEASE_ALL_SCRIPT.content,
            2,
            self.enqueue_key,
            self.execution_key,
            self.enqueue_owner,
            self.execution_owner,
        )
