import abc
from collections.abc import Callable
from typing import Any


class BaseMigrationStage(abc.ABC):
    @abc.abstractmethod
    async def process(self) -> Any: ...


class RunPythonMigrationStage(BaseMigrationStage):
    def __init__(self, callback: Callable) -> None:
        self.callback = callback

    async def process(self) -> Any:
        return self.callback()
