import json
from abc import abstractmethod
from collections.abc import Callable
from functools import partial
from typing import Any, overload, override

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession
from redis import exceptions as redis_exceptions
from redis.asyncio import Redis

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, MongoUpdateOperator
from saltbox_sdk.db.mongo.schemas_base import EmptyModel, PyObjectId
from saltbox_sdk.db.mongo.transaction import _get_managed_transaction
from saltbox_sdk.exceptions import ObjectNotFoundException
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
        self._check_notify_session(session=session, notify=notify)
        obj_id = await super().create(data=data, session=session)

        if notify is True:
            await self._notify(obj_id=obj_id, action='create', session=session)

        return obj_id

    @override
    async def bulk_create(
        self,
        data: list[CreateSchema] | list[dict[str, Any]],
        *,
        session: MongoAsyncClientSession | None = None,
        notify: bool = True,
    ) -> list[PyObjectId]:
        self._check_notify_session(session=session, notify=notify)
        obj_ids = await super().bulk_create(data=data, session=session)

        if notify is True:
            for obj_id in obj_ids:
                await self._notify(obj_id=obj_id, action='create', session=session)

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
        self._check_notify_session(session=session, notify=notify)
        obj_id = await super().update(
            query=query, data=data, exclude_unset=exclude_unset, operator=operator, session=session
        )

        if notify is True:
            await self._notify(obj_id=obj_id, action='update', session=session)

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
        self._check_notify_session(session=session, notify=notify)
        obj_ids = await super().bulk_update(
            query=query, data=data, exclude_unset=exclude_unset, operator=operator, session=session
        )

        if notify is True:
            for obj_id in obj_ids:
                await self._notify(obj_id=obj_id, action='update', session=session)

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
        self._check_notify_session(session=session, notify=notify)
        if isinstance(query, PyObjectId):
            obj_id = query
        else:
            obj_id = (await self.get(query=query, session=session, projection_model=EmptyModel)).id
        deleted_count = await super().delete(query=obj_id, session=session)

        if notify is True and deleted_count:
            await self._notify(obj_id=obj_id, action='delete', session=session)

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
        if isinstance(query, PyObjectId):
            query = {'_id': query}

        self._check_notify_session(session=session, notify=notify)
        objs = await self.get_list(query=query, session=session, projection_model=EmptyModel)
        if not objs:
            return 0

        deleted_count = await super().delete_many(query={'_id': {'$in': [obj.id for obj in objs]}}, session=session)
        if notify is True and deleted_count:
            for obj in objs:
                await self._notify(obj_id=obj.id, action='delete', session=session)

        return deleted_count

    def _get_notify_channel(self, obj: BaseModel, action: str) -> str | None:
        return None

    @staticmethod
    def _check_notify_session(session: MongoAsyncClientSession | None, notify: bool) -> None:
        if notify is True:
            _get_managed_transaction(session)

    async def _notify(self, obj_id: PyObjectId, action: str, *, session: MongoAsyncClientSession | None = None) -> None:
        tx = _get_managed_transaction(session)
        if tx is not None:
            tx.on_commit(partial(self._notify, obj_id=obj_id, action=action))
            return

        try:
            await self.notify_taskiq_task.kiq(service_name=self.service_name, document_id=str(obj_id), action=action)  # type: ignore
        except TaskAlreadyRunningException as e:
            logger.debug(str(e))

    async def run_notify(self, obj_id: PyObjectId, action: str) -> None:
        if action == 'delete':
            await self.run_delete_notify(obj_id=obj_id)
            return

        try:
            obj = await self.get(query=obj_id, projection_model=self.notify_schema)
            channel = self._get_notify_channel(obj=obj, action=action)

            if channel:
                await self.rdb.publish(channel=channel, message=self._prepare_pub_message(obj=obj))
        except redis_exceptions.RedisError as e:
            logger.error(e)
        except ObjectNotFoundException:
            logger.debug(f'Object "{self.repo.Meta.collection_name}" for notifying not found by query: {obj_id}')

    async def run_delete_notify(self, obj_id: PyObjectId) -> None:
        obj = EmptyModel(_id=obj_id)
        channel = self._get_notify_channel(obj=obj, action='delete') or f'{self.service_name}:{obj_id}:delete'
        try:
            await self.rdb.publish(channel=channel, message=json.dumps({'id': str(obj_id)}))
        except redis_exceptions.RedisError as e:
            logger.error(e)

    @staticmethod
    def _prepare_pub_message(obj: BaseModel) -> str:
        data = obj.model_dump(by_alias=True, mode='json')

        if 'id' in data:
            data['_id'] = data['id']

        return json.dumps(data)
