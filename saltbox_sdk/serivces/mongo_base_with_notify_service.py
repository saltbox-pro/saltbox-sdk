import json
from typing import Any, overload, override

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession
from redis.asyncio import Redis

from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, ProjectionModel
from saltbox_sdk.db.mongo.schemas_base import PyObjectId
from saltbox_sdk.serivces.mongo_base_service import MongoBaseService


class MongoBaseWithNotifyService[
    Repository: BaseMongoRepository,
    ModelType: BaseModel,
    CreateSchema: BaseModel,
    UpdateSchema: BaseModel,
](
    MongoBaseService[Repository, ModelType, CreateSchema, UpdateSchema],
):
    def __init__(
        self,
        repo: Repository,
        rdb: Redis,
    ):
        super().__init__(repo=repo)

        self.rdb = rdb

    @overload
    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> ModelType: ...

    @overload
    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
        notify: bool = True,
    ) -> ProjectionModel: ...

    @override
    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        notify: bool = True,
    ) -> ModelType | ProjectionModel:
        obj: ModelType | ProjectionModel

        if projection_model:
            obj = await super().create(data=data, projection_model=projection_model, session=session)
        else:
            obj = await super().create(data=data, session=session)

        if notify and hasattr(obj, 'id'):
            await self._notify(obj=obj, action='create')

        return obj

    @overload
    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
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
        notify: bool = True,
    ) -> ProjectionModel: ...

    @override
    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        notify: bool = True,
    ) -> ModelType | ProjectionModel:
        obj: ModelType | ProjectionModel

        if projection_model:
            obj = await super().update(
                query=query, data=data, exclude_unset=exclude_unset, projection_model=projection_model, session=session
            )
        else:
            obj = await super().update(query=query, data=data, exclude_unset=exclude_unset, session=session)

        if isinstance(notify, bool) and notify and hasattr(obj, 'id'):
            await self._notify(obj=obj, action='update')

        return obj

    @overload
    async def delete(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int: ...

    @overload
    async def delete(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> int: ...

    @override
    async def delete(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> int:
        obj = await self.get(query=query, session=session)
        deleted_count = await super().delete(query=query, session=session)

        if notify:
            await self._notify(obj=obj, action='delete')

        return deleted_count

    @overload
    async def delete_many(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int: ...

    @overload
    async def delete_many(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> int: ...

    @override
    async def delete_many(
        self,
        query: dict[str, Any] | PyObjectId,
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> int:
        objs = await self.get_list(query=query, session=session)
        deleted_count = await super().delete(query=query, session=session)

        for obj in objs:
            if isinstance(notify, bool) and notify:
                await self._notify(obj=obj, action='delete')

        return deleted_count

    def _get_notify_channel(self, obj: BaseModel | ProjectionModel, action: str) -> str | None:
        return None

    async def _notify(self, obj: BaseModel | ProjectionModel, action: str) -> None:
        channel = self._get_notify_channel(obj=obj, action=action)

        if channel:
            await self.rdb.publish(channel=channel, message=self._prepare_pub_message(obj=obj))

    @staticmethod
    def _prepare_pub_message(obj: BaseModel | ProjectionModel) -> str:
        data = obj.model_dump(by_alias=True, mode='json')

        if 'id' in data:
            data['_id'] = data['id']

        return json.dumps(data)
