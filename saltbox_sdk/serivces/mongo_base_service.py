from collections.abc import AsyncIterator
from typing import Any, TypeVar, overload

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession

from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, MongoUpdateOperator
from saltbox_sdk.db.mongo.schemas_base import PyObjectId, SortOrder
from saltbox_sdk.db.schemas_base import PaginatedResponse
from saltbox_sdk.serivces.abc_service import AbstractService

ProjectionModel = TypeVar('ProjectionModel', bound=BaseModel)
StubDefault: Any = None


class MongoBaseService[
    Repository: BaseMongoRepository,
    ModelType: BaseModel,
    CreateSchema: BaseModel,
    UpdateSchema: BaseModel,
](AbstractService[Repository]):
    @overload
    async def get(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> ModelType: ...

    @overload
    async def get(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def get(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> ModelType | ProjectionModel:
        if isinstance(query, PyObjectId):
            query = {'_id': query}

        if projection_model:
            result = await self.repo.get(query=query, projection_model=projection_model, session=session)
        else:
            result = await self.repo.get(query=query, session=session)

        return result

    @overload
    async def get_list(
        self,
        query: Any,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ModelType]: ...

    @overload
    async def get_list(
        self,
        query: Any,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] = StubDefault,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ProjectionModel]: ...

    async def get_list(
        self,
        query: Any,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ModelType] | list[ProjectionModel]:
        if projection_model:
            result: list[ProjectionModel] = await self.repo.get_list(
                query=query, sort=sort, limit=limit, skip=skip, projection_model=projection_model, session=session
            )
            return result

        return await self.repo.get_list(query=query, sort=sort, limit=limit, skip=skip, session=session)

    @overload
    def iter_list(
        self,
        query: Any,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> AsyncIterator[ModelType]: ...

    @overload
    def iter_list(
        self,
        query: Any,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] = StubDefault,
        sort: dict[str, SortOrder] | None = None,
    ) -> AsyncIterator[ProjectionModel]: ...

    async def iter_list(
        self,
        query: Any,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> AsyncIterator[ModelType] | AsyncIterator[ProjectionModel]:
        if projection_model:
            async for item in self.repo.iter_list(
                query=query, sort=sort, limit=limit, skip=skip, projection_model=projection_model, session=session
            ):
                yield item
        else:
            async for item in self.repo.iter_list(query=query, sort=sort, limit=limit, skip=skip, session=session):
                yield item

    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        return await self.repo.create(data=data, session=session)

    async def bulk_create(
        self,
        data: list[CreateSchema] | list[dict[str, Any]],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> list[PyObjectId]:
        return await self.repo.bulk_create(data=data, session=session)

    @overload
    async def get_list_paginated(
        self,
        query: dict[str, Any] | None,
        limit: int,
        skip: int,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> PaginatedResponse[ModelType]: ...

    @overload
    async def get_list_paginated(
        self,
        query: dict[str, Any] | None,
        limit: int,
        skip: int,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
        sort: dict[str, SortOrder] | None = None,
    ) -> PaginatedResponse[ProjectionModel]: ...

    async def get_list_paginated(
        self,
        query: dict[str, Any] | None = None,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> PaginatedResponse[ModelType] | PaginatedResponse[ProjectionModel]:
        total = await self.repo.count(query)

        if projection_model:
            data = await self.repo.get_list(
                query, sort=sort, limit=limit, skip=skip, projection_model=projection_model, session=session
            )
            return PaginatedResponse[ProjectionModel](total=total, data=data)
        else:
            data = await self.repo.get_list(query, sort=sort, limit=limit, skip=skip, session=session)
            return PaginatedResponse[ModelType](total=total, data=data)

    async def count(
        self,
        query: dict[str, Any] | None = None,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        return await self.repo.count(query=query, session=session)

    async def exists(
        self,
        query: dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> bool:
        return await self.repo.exists(query=query, session=session)

    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        return await self.repo.update(
            query=query, data=data, exclude_unset=exclude_unset, operator=operator, session=session
        )

    async def update_or_create(
        self,
        query: dict[str, Any],
        data: dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        return await self.repo.update(
            query=query, data=data, exclude_unset=exclude_unset, upsert=True, operator=operator, session=session
        )

    async def bulk_update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
    ) -> list[PyObjectId]:
        return await self.repo.bulk_update(
            query=query, data=data, exclude_unset=exclude_unset, operator=operator, session=session
        )

    async def delete(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        if isinstance(query, PyObjectId):
            query = {'_id': query}

        return await self.repo.delete(query=query, session=session)

    async def delete_many(
        self,
        query: dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        return await self.repo.delete_many(query=query, session=session)
