from typing import Any, ClassVar, overload, override

from pydantic import BaseModel
from pymongo.asynchronous.client_session import (
    AsyncClientSession as MongoAsyncClientSession,
)
from pymongo.errors import CollectionInvalid, OperationFailure
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, ModelType, MongoUpdateOperator, ProjectionModel
from saltbox_sdk.db.mongo.schemas_base import PyObjectId, SortOrder, TimeSeriesConfig
from saltbox_sdk.db.schemas_base import CursoredTimeseriesResponse
from saltbox_sdk.exceptions import DuplicateKeyException, ObjectCreateException


class TimeSeriesRepository[T: BaseModel](BaseMongoRepository[T]):
    class Meta(BaseMongoRepository.Meta):
        timeseries: ClassVar[TimeSeriesConfig]
        expire_after_seconds: ClassVar[int | None] = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        ts = cls.Meta.timeseries

        # Runtime-check
        if not ts or 'timeField' not in ts:
            msg = "Meta.timeseries['timeField'] is required"  # type: ignore[unreachable]
            raise ValueError(msg) from None

        time_f = ts['timeField']
        meta_f = ts.get('metaField')
        allowed = {time_f, meta_f} if meta_f else {time_f}

        for idx_keys in (getattr(cls.Meta, 'collection_index_to_keys', {}) or {}).values():
            if not idx_keys or idx_keys[0][0] not in allowed:
                msg = f'Index {idx_keys} must start with timeField=`{time_f}` or metaField=`{meta_f}`'
                raise ValueError(msg)

    async def create_collection(self) -> None:
        ts_config = self.Meta.timeseries
        opts: dict[str, Any] = {'timeseries': ts_config}

        if ttl := self.Meta.expire_after_seconds:
            opts['expireAfterSeconds'] = int(ttl)
        try:
            await self._database.create_collection(self.Meta.collection_name, **opts)
            logger.debug(f'TS Collection `{self.Meta.collection_name}` created')
        except CollectionInvalid:
            pass  # Collection already exists

        await self._update_ts_indexes()
        await self._post_create_collection()

    async def _update_ts_indexes(self) -> None:
        expected = dict(getattr(self.Meta, 'collection_index_to_keys', {}) or {})
        options = dict(getattr(self.Meta, 'collection_index_options', {}) or {})

        ts = self.Meta.timeseries
        time_f, meta_f = ts['timeField'], ts.get('metaField')
        auto_name = f'{meta_f}_1_{time_f}_1' if meta_f else f'{time_f}_1'
        expected[auto_name] = [(meta_f, 1), (time_f, 1)] if meta_f else [(time_f, 1)]

        existing = await self.collection.index_information()
        existing_names = set(existing.keys())

        for idx_name in existing_names - {'_id_'}:
            if idx_name not in expected:
                try:
                    await self.collection.drop_index(idx_name)
                except OperationFailure:
                    pass  # MongoDB won't allow dropping system/auto indexes

        for idx_name, keys in expected.items():
            if idx_name not in existing_names:
                idx_opts = options.get(idx_name, {})
                await self.collection.create_index(keys, name=idx_name, **idx_opts)

    async def create(
        self,
        data: ModelType | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        prepared_data = await self.prepare_creation_data(data=data)

        try:
            result = await self.collection.insert_one(document=prepared_data, session=session)
        except MongoDuplicateKeyError as e:
            if e.details and 'keyValue' in e.details:
                raise DuplicateKeyException(key_value=e.details['keyValue']) from None
            raise DuplicateKeyException(str(e)) from None

        if not result.inserted_id:
            raise ObjectCreateException()

        # TODO: check this logic
        prepared_data['_id'] = result.inserted_id

        return PyObjectId(result.inserted_id)

    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        upsert: bool = False,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        msg = 'TimeSeriesRepository does not support update. Time series documents are append-only by design.'
        raise NotImplementedError(msg)

    @override
    async def delete(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        msg = (
            'TimeSeriesRepository does not support single-document delete. '
            'Use delete_many() with a time-range filter instead.'
        )
        raise NotImplementedError(msg)

    # TODO: refactor get_list_in_range and get_list_in_range_paginated
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
    ) -> list[T]: ...

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
    ) -> list[T] | list[ProjectionModel]:
        """Cursor-based pagination for time series data. Returns documents with
        timeField in [time_from, time_to) range, sorted by timeField ascending by default.
        """
        time_f = self.Meta.timeseries['timeField']
        query: dict[str, Any] = {time_f: {'$gte': time_from, '$lt': time_to}}
        if extra_filter:
            query.update(extra_filter)

        if projection_model is not None:
            result = await self.get_list(
                query=query,
                limit=limit,
                skip=0,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
            return result
        return await self.get_list(query=query, limit=limit, skip=0, sort=sort, session=session)

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
    ) -> CursoredTimeseriesResponse[T]: ...

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
    ) -> CursoredTimeseriesResponse[T] | CursoredTimeseriesResponse[ProjectionModel]:
        if projection_model is not None:
            data_pm = await self.get_list_in_range(
                time_from,
                time_to,
                extra_filter=extra_filter,
                limit=limit,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
            next_cursor = None
            if len(data_pm) == limit:
                time_f = self.Meta.timeseries['timeField']
                next_cursor = getattr(data_pm[-1], time_f, None)
            return CursoredTimeseriesResponse(data=data_pm, next_cursor=next_cursor)

        data_t = await self.get_list_in_range(
            time_from,
            time_to,
            extra_filter=extra_filter,
            limit=limit,
            sort=sort,
            session=session,
        )
        next_cursor = None
        if len(data_t) == limit:
            time_f = self.Meta.timeseries['timeField']
            next_cursor = getattr(data_t[-1], time_f, None)
        return CursoredTimeseriesResponse(data=data_t, next_cursor=next_cursor)
