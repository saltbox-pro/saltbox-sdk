from typing import Any, overload

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession

from saltbox_sdk.db.mongo.repository_time_series_base import TimeSeriesRepository
from saltbox_sdk.db.mongo.schemas_base import SortOrder
from saltbox_sdk.db.schemas_base import CursoredTimeseriesResponse
from saltbox_sdk.serivces.mongo_base_service import MongoBaseService, ProjectionModel


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
            result: list[ProjectionModel] = await self.repo.get_list_in_range(
                time_from,
                time_to,
                extra_filter=extra_filter,
                limit=limit,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
            return result
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
            result: CursoredTimeseriesResponse[ProjectionModel] = await self.repo.get_list_in_range_paginated(
                time_from,
                time_to,
                extra_filter=extra_filter,
                limit=limit,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
            return result
        return await self.repo.get_list_in_range_paginated(
            time_from,
            time_to,
            extra_filter=extra_filter,
            limit=limit,
            sort=sort,
            session=session,
        )
