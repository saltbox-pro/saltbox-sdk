from typing import Any, TypeVar, overload

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession

from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, TimeSeriesRepository
from saltbox_sdk.db.mongo.schemas_base import PyObjectId, SortOrder
from saltbox_sdk.db.schemas_base import CursoredTimeseriesResponse, PaginatedResponse
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
            return await self.repo.get_list(
                query=query, sort=sort, limit=limit, skip=skip, projection_model=projection_model, session=session
            )

        return await self.repo.get_list(query=query, sort=sort, limit=limit, skip=skip, session=session)

    @overload
    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> ModelType: ...

    @overload
    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> ModelType | ProjectionModel:
        if projection_model:
            result = await self.repo.create(data=data, projection_model=projection_model, session=session)
        else:
            result = await self.repo.create(data=data, session=session)

        return result

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

    @overload
    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> ModelType: ...

    @overload
    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> ModelType | ProjectionModel:
        if isinstance(query, PyObjectId):
            query = {'_id': query}

        if projection_model:
            result = await self.repo.update(
                query=query, data=data, projection_model=projection_model, exclude_unset=exclude_unset, session=session
            )
        else:
            result = await self.repo.update(query=query, data=data, exclude_unset=exclude_unset, session=session)

        return result

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


class MongoTimeseriesBaseService[
    Repository: TimeSeriesRepository,
    ModelType: BaseModel,
    CreateSchema: BaseModel,
](MongoBaseService[Repository, ModelType, CreateSchema, BaseModel]):
    @overload
    async def get_list_in_range(
        self,
        time_from: Any,
        time_to: Any,
        *,
        extra_filter: dict[str, Any] | None = None,
        limit: int = 0,
        sort: dict[str, SortOrder] | None = None,
        session: MongoAsyncClientSession | None = None,
    ) -> list[ModelType]: ...

    @overload
    async def get_list_in_range(
        self,
        time_from: Any,
        time_to: Any,
        *,
        extra_filter: dict[str, Any] | None = None,
        limit: int = 0,
        sort: dict[str, SortOrder] | None = None,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> list[ProjectionModel]: ...

    async def get_list_in_range(
        self,
        time_from: Any,
        time_to: Any,
        *,
        extra_filter: dict[str, Any] | None = None,
        limit: int = 0,
        sort: dict[str, SortOrder] | None = None,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> list[ModelType] | list[ProjectionModel]:
        if projection_model is not None:
            return await self.repo.get_list_in_range(
                time_from,
                time_to,
                extra_filter=extra_filter,
                limit=limit,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
        return await self.repo.get_list_in_range(
            time_from,
            time_to,
            extra_filter=extra_filter,
            limit=limit,
            sort=sort,
            session=session,
        )

    @overload
    async def get_list_in_range_paginated(
        self,
        time_from: Any,
        time_to: Any,
        *,
        extra_filter: dict[str, Any] | None = None,
        limit: int = 50,
        sort: dict[str, SortOrder] | None = None,
        session: MongoAsyncClientSession | None = None,
    ) -> CursoredTimeseriesResponse[ModelType]: ...

    @overload
    async def get_list_in_range_paginated(
        self,
        time_from: Any,
        time_to: Any,
        *,
        extra_filter: dict[str, Any] | None = None,
        limit: int = 50,
        sort: dict[str, SortOrder] | None = None,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> CursoredTimeseriesResponse[ProjectionModel]: ...

    async def get_list_in_range_paginated(
        self,
        time_from: Any,
        time_to: Any,
        *,
        extra_filter: dict[str, Any] | None = None,
        limit: int = 50,
        sort: dict[str, SortOrder] | None = None,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> CursoredTimeseriesResponse[ModelType] | CursoredTimeseriesResponse[ProjectionModel]:
        if projection_model is not None:
            return await self.repo.get_list_in_range_paginated(
                time_from,
                time_to,
                extra_filter=extra_filter,
                limit=limit,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
        return await self.repo.get_list_in_range_paginated(
            time_from,
            time_to,
            extra_filter=extra_filter,
            limit=limit,
            sort=sort,
            session=session,
        )
