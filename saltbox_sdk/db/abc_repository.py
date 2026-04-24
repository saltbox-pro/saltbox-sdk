from abc import ABC, abstractmethod
from functools import cached_property
from typing import Any, cast

from pydantic import BaseModel


class AbstractRepository[T: BaseModel](ABC):
    @cached_property
    def default_model(self) -> type[T]:
        return cast(type[T], self.__orig_bases__[0].__args__[0])  # type: ignore[attr-defined]

    @abstractmethod
    async def get(self, *args: Any, **kwargs: Any) -> T: ...

    @abstractmethod
    async def get_list(self, *args: Any, **kwargs: Any) -> list[T]: ...

    @abstractmethod
    async def count(self, *args: Any, **kwargs: Any) -> int: ...

    @abstractmethod
    async def exists(self, *args: Any, **kwargs: Any) -> int: ...

    @abstractmethod
    async def create(self, *args: Any, **kwargs: Any) -> Any: ...

    @abstractmethod
    async def bulk_create(self, *args: Any, **kwargs: Any) -> list: ...

    @abstractmethod
    async def update(self, *args: Any, **kwargs: Any) -> Any: ...

    # @abstractmethod
    # async def bulk_update(self, *args: Any, **kwargs: Any) -> list: ...

    @abstractmethod
    async def delete(self, *args: Any, **kwargs: Any) -> int: ...
