import abc
import inspect
from collections.abc import Callable
from typing import Any


class BaseMigrationStage(abc.ABC):
    @abc.abstractmethod
    async def process(self) -> Any: ...


class RunPythonMigrationStage(BaseMigrationStage):
    def __init__(self, callback: Callable) -> None:
        self.callback = callback

    async def process(self) -> Any:
        result = self.callback()

        if inspect.isawaitable(result):
            return await result

        return result
