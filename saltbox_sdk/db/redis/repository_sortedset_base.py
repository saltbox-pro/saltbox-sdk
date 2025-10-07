import json
from datetime import UTC, datetime
from typing import Any, TypeVar, overload

from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import ResponseError as RedisResponseError

# from sa.saltbox_sdk import logger
from saltbox_sdk.db.abc_repository import AbstractRepository
from saltbox_sdk.db.redis.schemas_base import SortedSetId
from saltbox_sdk.exceptions import (
    MultipleObjectsFoundException,
    ObjectNotFoundException,
    ObjectUpdateException,
    RepositoryException,
    SaltBoxValidationException,
)

ProjectionModel = TypeVar('ProjectionModel', bound=BaseModel)
ModelType = TypeVar('ModelType', bound=BaseModel)


class SortedsetRedisRepository[T: BaseModel](AbstractRepository[T]):
    class Meta:
        collection_name: str
        id_field_name: str = 'id'
        auto_now_add_fields: list[str]
        auto_now_fields: list[str]
        query_overrides: dict[str, str]

    def __init__(self, database: Redis):
        super().__init__()
        self._database: Redis = database
        self.__validate()

    def __validate(self) -> None:
        if self.Meta.id_field_name not in self.default_model.model_fields:
            msg = 'Document class should have `id` field'
            raise SaltBoxValidationException(msg)
        if not hasattr(self.Meta, 'collection_name') or not self.Meta.collection_name:
            msg = 'Meta should contain `collection_name`'
            raise SaltBoxValidationException(msg)
        if hasattr(self.Meta, 'auto_now_add_fields') and self.Meta.auto_now_add_fields:
            for field in self.Meta.auto_now_add_fields:
                if field not in self.default_model.model_fields:
                    msg = f'Meta `auto_now_add_fields` `{field}` should be in model fields'
                    raise SaltBoxValidationException(msg.format(field, self.Meta.collection_name))
        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                if field not in self.default_model.model_fields:
                    msg = f'Meta `auto_now_fields` `{field}` should be in model fields'
                    raise SaltBoxValidationException(msg.format(field, self.Meta.collection_name))

    @classmethod
    def _generate_id(cls, data: T | dict[str, Any]) -> SortedSetId:
        return datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')

    @overload
    async def get(self, query: SortedSetId | int | float) -> T: ...

    @overload
    async def get(
        self, query: SortedSetId | int | float, projection_model: type[ProjectionModel]
    ) -> ProjectionModel: ...

    async def get(
        self, query: SortedSetId | int | float, projection_model: type[ProjectionModel] | None = None
    ) -> ProjectionModel | T:
        if type(query) in [int, float]:
            query = str(query)

        result = await self._database.zrange(
            name=self.Meta.collection_name,
            start=query,  # type: ignore
            end=query,  # type: ignore
            byscore=True,
        )

        if len(result) == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query={'id': query})
        elif len(result) > 1:
            raise MultipleObjectsFoundException()

        data = json.loads(result[0].decode())
        data['id'] = query

        if projection_model is not None:
            return projection_model.model_validate(data)
        else:
            return self.default_model.model_validate(data)

    async def zscan(
        self, cursor: int = 0, match: str | None = None, count: int | None = None
    ) -> tuple[int, list[tuple[str, float]]]:
        try:
            return await self._database.zscan(name=self.Meta.collection_name, cursor=cursor, match=match, count=count)
        except RedisResponseError as e:
            if 'invalid cursor' in str(e):
                msg = f'Invalid cursor: {cursor}'
                raise SaltBoxValidationException(msg) from None
            raise RepositoryException(str(e)) from None

    @overload
    async def get_list(self, start: int, end: int | None, limit: int | None, skip: int, desc: bool) -> list[T]: ...

    @overload
    async def get_list(
        self,
        start: int,
        end: int | None,
        limit: int | None,
        skip: int,
        desc: bool,
        projection_model: type[ProjectionModel],
    ) -> list[ProjectionModel]: ...

    async def get_list(
        self,
        start: int = 0,
        end: int | None = None,
        limit: int | None = None,
        skip: int = 0,
        desc: bool = False,
        projection_model: type[ProjectionModel] | None = None,
    ) -> list[T] | list[ProjectionModel]:
        result_ = await self._database.zrange(
            name=self.Meta.collection_name,
            start=start,
            end=-1 if end is None else end,
            desc=desc,
            offset=skip,
            num=limit,
            withscores=True,
            byscore=True,
        )

        result = [{'id': str(int(obj[1])), **json.loads(obj[0].decode())} for obj in result_]

        if projection_model:
            return [projection_model.model_validate(obj) for obj in result]
        else:
            return [self.default_model.model_validate(obj) for obj in result]

    async def count(
        self, start: SortedSetId | int | float | None = None, end: SortedSetId | int | float | None = None
    ) -> int:
        start = start or float('-inf')
        end = end or float('inf')

        return await self._database.zcount(
            name=self.Meta.collection_name,
            min=min(start, end),
            max=max(start, end),
        )

    async def exists(self, query: SortedSetId) -> bool:
        return await self._database.zcount(name=self.Meta.collection_name, min=int(query), max=int(query)) == 1

    @overload
    async def create(self, data: ModelType | dict[str, Any]) -> T: ...

    @overload
    async def create(
        self, data: ModelType | dict[str, Any], projection_model: type[ProjectionModel]
    ) -> ProjectionModel: ...

    async def create(
        self,
        data: ModelType | dict[str, Any],
        projection_model: type[ProjectionModel] | None = None,
    ) -> T | ProjectionModel:
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude={'id'}, mode='json')  # probably don't need to exclude id
        else:
            if 'id' in data.keys():
                del data['id']

        obj_id: SortedSetId = self._generate_id(data=data)

        if hasattr(self.Meta, 'auto_now_add_fields') and self.Meta.auto_now_add_fields:
            for field in self.Meta.auto_now_add_fields:
                data[field] = datetime.now(UTC).timestamp()
        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                data[field] = datetime.now(UTC).timestamp()

        await self._database.zadd(
            name=self.Meta.collection_name,
            mapping={json.dumps(data): obj_id},
        )

        if projection_model:
            return await self.get(obj_id, projection_model=projection_model)
        else:
            return await self.get(obj_id)

    @overload
    async def update(
        self,
        query: SortedSetId,
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
    ) -> T: ...

    @overload
    async def update(
        self,
        query: SortedSetId,
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def update(
        self,
        query: SortedSetId,
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        projection_model: type[ProjectionModel] | None = None,
    ) -> T | ProjectionModel:
        if isinstance(data, BaseModel):
            data = data.model_dump(exclude={'id'}, exclude_unset=exclude_unset, mode='json')

        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                data[field] = datetime.now(UTC)

        await self.get(query=query)
        await self.delete(query=query)

        updated_count = await self._database.zadd(
            name=self.Meta.collection_name,
            mapping={json.dumps(data): int(query)},
        )

        if updated_count != 1:
            raise ObjectUpdateException()

        if projection_model:
            return await self.get(query, projection_model=projection_model)
        else:
            return await self.get(query)

    async def delete(self, query: SortedSetId) -> int:
        await self.get(query=query)
        await self._database.zrem(self.Meta.collection_name, query)

        return 1
