import json
from abc import abstractmethod
from collections.abc import Callable
from typing import Any, overload, override

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession
from redis.asyncio import Redis

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, MongoUpdateOperator
from saltbox_sdk.db.mongo.schemas_base import EmptyModel, PyObjectId
from saltbox_sdk.serivces.mongo_base_service import MongoBaseService
from saltbox_sdk.utilities.taskiq import TaskAlreadyRunningException


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

    @property
    @abstractmethod
    def notify_taskiq_task(self) -> Callable: ...

    @property
    def notify_schema(self) -> type[BaseModel]:
        return self.repo.default_model

    @property
    @abstractmethod
    def service_name(self) -> str: ...

    @override
    async def create(
        self,
        data: CreateSchema | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> PyObjectId:
        obj_id = await super().create(data=data, session=session)

        if isinstance(notify, bool) and notify:
            await self._notify(obj_id=obj_id, action='create')

        return obj_id

    @override
    async def bulk_create(
        self,
        data: list[CreateSchema] | list[dict[str, Any]],
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> list[PyObjectId]:
        obj_ids = await super().bulk_create(data=data, session=session)

        if isinstance(notify, bool) and notify:
            for obj_id in obj_ids:
                await self._notify(obj_id=obj_id, action='create')

        return obj_ids

    async def update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> PyObjectId:
        obj_id = await super().update(
            query=query, data=data, exclude_unset=exclude_unset, operator=operator, session=session
        )

        if isinstance(notify, bool) and notify:
            await self._notify(obj_id=obj_id, action='update')

        return obj_id

    async def bulk_update(
        self,
        query: dict[str, Any] | PyObjectId,
        data: UpdateSchema | dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> list[PyObjectId]:
        obj_ids = await super().bulk_update(
            query=query, data=data, exclude_unset=exclude_unset, operator=operator, session=session
        )

        if isinstance(notify, bool) and notify:
            for obj_id in obj_ids:
                await self._notify(obj_id=obj_id, action='update')

        return obj_ids

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
        obj = await self.get(query=query, session=session, projection_model=EmptyModel)
        deleted_count = await super().delete(query=obj.id, session=session)

        if isinstance(notify, bool) and notify:
            await self._notify(obj_id=obj.id, action='delete')

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
        objs = await self.get_list(query=query, session=session, projection_model=EmptyModel)
        deleted_count = await super().delete(query={'_id': {'$in': [obj.id for obj in objs]}}, session=session)

        for obj in objs:
            if isinstance(notify, bool) and notify:
                await self._notify(obj_id=obj.id, action='delete')

        return deleted_count

    def _get_notify_channel(self, obj: BaseModel, action: str) -> str | None:
        return None

    async def _notify(self, obj_id: PyObjectId, action: str) -> None:
        try:
            await self.notify_taskiq_task.kiq(service_name=self.service_name, document_id=str(obj_id), action=action)  # type: ignore
        except TaskAlreadyRunningException as e:
            logger.debug(str(e))

    async def run_notify(self, obj_id: PyObjectId, action: str) -> None:
        obj = await self.get(query=obj_id, projection_model=self.notify_schema)
        channel = self._get_notify_channel(obj=obj, action=action)

        if channel:
            await self.rdb.publish(channel=channel, message=self._prepare_pub_message(obj=obj))

    @staticmethod
    def _prepare_pub_message(obj: BaseModel) -> str:
        data = obj.model_dump(by_alias=True, mode='json')

        if 'id' in data:
            data['_id'] = data['id']

        return json.dumps(data)
