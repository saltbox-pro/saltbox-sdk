from collections.abc import Callable
from enum import StrEnum
from inspect import isclass
from typing import Any, ClassVar, TypeVar, cast, overload, override

from pydantic import BaseModel
from pymongo import AsyncMongoClient
from pymongo.asynchronous.client_session import (
    AsyncClientSession as MongoAsyncClientSession,
)
from pymongo.asynchronous.collection import AsyncCollection, ReturnDocument
from pymongo.asynchronous.command_cursor import AsyncCommandCursor
from pymongo.asynchronous.cursor import AsyncCursor
from pymongo.asynchronous.database import AsyncDatabase as MongoAsyncDatabase
from pymongo.errors import CollectionInvalid, InvalidName, OperationFailure
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
from pymongo.operations import _IndexKeyHint  # pyright: ignore[reportPrivateUsage]

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.config.mongo_config import MONGO_SETTINGS
from saltbox_sdk.db.abc_repository import AbstractRepository
from saltbox_sdk.db.mongo.aggregations import AggregationsStore
from saltbox_sdk.db.mongo.schemas_base import (
    EmptyModel,
    PyObjectId,
    SortOrder,
    TimeSeriesConfig,
)
from saltbox_sdk.db.schemas_base import CursoredTimeseriesResponse
from saltbox_sdk.exceptions import (
    DuplicateKeyException,
    MongoPipelineException,
    MultipleObjectsFoundException,
    ObjectCreateException,
    ObjectNotFoundException,
    ObjectUpdateException,
    SaltBoxValidationException,
)
from saltbox_sdk.utilities.helpers import recursive_replace_dates, utc_now

ProjectionModel = TypeVar('ProjectionModel', bound=BaseModel)
ModelType = TypeVar('ModelType', bound=BaseModel)


class MongoUpdateOperator(StrEnum):
    set = '$set'
    unset = '$unset'
    inc = '$inc'
    min = '$min'
    max = '$max'
    mul = '$mul'
    rename = '$rename'
    set_on_insert = '$setOnInsert'
    current_date = '$currentDate'  # Example: { field_name: { $type: "timestamp|date" } } }
    bit = '$bit'  # For bitwise operations `and`, `or` and `xor`: { $bit: { field_name: { and|or|xor: value } } }
    rand = '$rand'
    # For lists:
    add_to_set = '$addToSet'  # Can be used with `$each` modificator
    pop = '$pop'
    pull = '$pull'
    pull_all = '$pullAll'
    push = '$push'  # Can be used with `$each`, `$position`, `$slice` and `$sort` modificators


class BaseMongoRepository[T: BaseModel](AbstractRepository[T]):
    class Meta:
        collection_name: ClassVar[str]
        auto_now_add_fields: ClassVar[list[str]]
        auto_now_fields: ClassVar[list[str]]
        query_overrides: ClassVar[dict[str, str]]
        aggregations: ClassVar[AggregationsStore] = AggregationsStore()
        collection_index_to_keys: ClassVar[dict[str, _IndexKeyHint]]
        collection_index_options: ClassVar[dict[str, dict[str, Any]]] = {}

    def __init__(self, database: MongoAsyncDatabase[Any], **kwargs: Any) -> None:
        super().__init__()
        self._database: MongoAsyncDatabase[Any] = database
        self.__validate()

    @property
    def client(self) -> AsyncMongoClient[Any]:
        return self._database.client

    @property
    def collection(self) -> AsyncCollection[Any]:
        try:
            return self._database[self.Meta.collection_name]
        except InvalidName:
            logger.error(f'Collection `{self.Meta.collection_name}` does not exist.')
            raise

    @property
    def aggregations(self) -> AggregationsStore:
        if hasattr(self.Meta, 'aggregations') and self.Meta.aggregations:
            return self.Meta.aggregations

        return AggregationsStore()

    @property
    def __query_overrides__(self) -> dict[str, Callable]:
        query_overrides = {}

        if hasattr(self.Meta, 'query_overrides') and self.Meta.query_overrides:
            for (
                override_name,
                override_callback_name,
            ) in self.Meta.query_overrides.items():
                query_overrides[override_name] = getattr(self, override_callback_name)

        return query_overrides

    def __prepare_query__(  # noqa: C901
        self, query: PyObjectId | dict[str, Any] | None
    ) -> dict[str, Any]:
        if isinstance(query, PyObjectId):
            return {'_id': query}

        if query is None:
            return {}

        query_overrides = self.__query_overrides__

        def recursive_override(data: dict[str, Any]) -> dict[str, Any]:
            _query: dict[str, Any] = {}

            for data_key, data_value in data.items():
                if data_key in query_overrides.keys():
                    override_key, override_value = query_overrides[data_key](data_key, data_value)
                    if override_value is not None:
                        _query[override_key] = override_value
                else:
                    if data_value is None:
                        _query[data_key] = data_value
                    elif isinstance(data_value, dict):
                        _query[data_key] = recursive_override(data_value)
                    # TODO (i.moshkov): check if this is correct
                    elif isinstance(data_value, list) and data_key not in [
                        '$in',
                        '$nin',
                    ]:
                        _query[data_key] = [recursive_override(item_value) for item_value in data_value]
                    elif isinstance(data_value, PyObjectId):
                        _query[data_key] = data_value
                    else:
                        try:
                            _query['$or'] = [
                                {data_key: data_value},
                                {data_key: PyObjectId(data_value)},
                            ]
                        except Exception:
                            _query[data_key] = data_value
            return _query

        query = recursive_override(query)

        return cast(dict[str, Any], recursive_replace_dates(query))

    async def prepare_aggregation_pipeline(
        self,
        projection: dict[str, Any],
        query: dict[str, Any] | None = None,
        limit: int | None = None,
        skip: int | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[dict]:
        fields_names = list(projection.keys())

        def extract_fields_names_from_query(_query: dict[str, Any]) -> list[str]:
            res = []

            for field_name, field_value in _query.items():
                if field_name.startswith('$') and isinstance(field_value, dict):
                    res.extend(extract_fields_names_from_query(field_value))
                else:
                    res.append(field_name)

            return res

        if query:
            fields_names.extend(extract_fields_names_from_query(query))

        return self.aggregations.build_pipeline(fields_names=fields_names)

    async def prepare_pipeline(
        self,
        projection: dict[str, Any],
        query: dict[str, Any] | None = None,
        limit: int | None = None,
        skip: int | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[dict[str, Any]]:
        pipeline: list[dict[str, Any]] = await self.prepare_aggregation_pipeline(projection, query, limit, skip, sort)

        if pipeline:
            if query:
                pipeline.append({'$match': query})
            if sort:
                pipeline.append({'$sort': dict(sort)})
            if skip:
                pipeline.append({'$skip': skip})
            if limit:
                pipeline.append({'$limit': limit})

            pipeline.append({'$project': projection})

        return pipeline

    async def prepare_object_data(
        self,
        data: dict[str, Any],
        projection_model: type[ProjectionModel] | None = None,
    ) -> dict[str, Any]:
        return data

    async def prepare_creation_data(
        self,
        data: ModelType | dict[str, Any],
    ) -> dict[str, Any]:
        try:
            data = await self.validate_object_data(data)
        except ValueError as e:
            raise ObjectCreateException(str(e)) from e

        if isinstance(data, BaseModel):
            data_dict: dict[str, Any] = data.model_dump(exclude={'id'})
        else:
            data_dict = dict(data)

        now = utc_now()
        if hasattr(self.Meta, 'auto_now_add_fields') and self.Meta.auto_now_add_fields:
            for field in self.Meta.auto_now_add_fields:
                data_dict[field] = now
        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                data_dict[field] = now

        return data_dict

    @overload
    async def validate_object_data(self, data: ModelType) -> ModelType: ...

    @overload
    async def validate_object_data(self, data: dict[str, Any]) -> dict[str, Any]: ...

    async def validate_object_data(self, data: ModelType | dict[str, Any]) -> ModelType | dict[str, Any]:
        return data

    def __validate(self) -> None:
        if 'id' not in self.default_model.model_fields:
            msg = 'Document class should have `id` field'
            raise SaltBoxValidationException(msg)

        if not hasattr(self.Meta, 'collection_name') or not self.Meta.collection_name:
            msg = 'Meta should contain `collection_name`'
            raise SaltBoxValidationException(msg)

        if hasattr(self.Meta, 'auto_now_add_fields') and self.Meta.auto_now_add_fields:
            for field in self.Meta.auto_now_add_fields:
                if field not in self.default_model.model_fields:
                    msg = f'Meta `auto_now_add_fields` `{field}` should be in model fields'
                    pretty_msg = msg.format(field, self.Meta.collection_name)
                    raise SaltBoxValidationException(pretty_msg)

        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                if field not in self.default_model.model_fields:
                    msg = f'Meta `auto_now_fields` `{field}` should be in model fields'
                    pretty_msg = msg.format(field, self.Meta.collection_name)
                    raise SaltBoxValidationException(pretty_msg)

    @classmethod
    def _get_projection_from_model(cls, model: type[BaseModel], path: list | None = None) -> dict[str, Any]:
        projection = {}
        if not path:
            path = []

        for field_name, field in model.model_fields.items():
            if field.annotation and isclass(field.annotation) and issubclass(field.annotation, BaseModel):
                sub_model = field.annotation
                projection.update(cls._get_projection_from_model(sub_model, [*path, field_name]))
            else:
                if field.alias:
                    computed_field_name = field.alias
                else:
                    computed_field_name = field_name

                projection['.'.join([*path, computed_field_name])] = 1

        return projection

    @overload
    async def get(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> T: ...

    @overload
    async def get(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def get(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> ProjectionModel | T:
        if projection_model:
            projection = self._get_projection_from_model(projection_model)
        else:
            projection = self._get_projection_from_model(self.default_model)
        query = self.__prepare_query__(query)
        pipeline = await self.prepare_pipeline(projection, query)

        if pipeline:
            if MONGO_SETTINGS.mongo_explain:
                explanation = await self._database.command(
                    'aggregate', self.Meta.collection_name, pipeline=pipeline, explain=True
                )
                logger.debug(explanation)

            result = await (await self.collection.aggregate(pipeline=pipeline, session=session)).to_list()
        else:
            cursor = self.collection.find(filter=query, projection=projection, session=session)

            if MONGO_SETTINGS.mongo_explain:
                logger.debug(await cursor.explain())

            result = await cursor.to_list()

        if len(result) == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif len(result) > 1:
            raise MultipleObjectsFoundException()

        data = await self.prepare_object_data(data=result[0], projection_model=projection_model)

        if projection_model is not None:
            return projection_model.model_validate(data)
        else:
            return self.default_model.model_validate(data)

    @overload
    async def get_list(
        self,
        query: dict[str, Any] | None,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T]: ...

    @overload
    async def get_list(
        self,
        query: dict[str, Any] | None,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ProjectionModel]: ...

    async def get_list(
        self,
        query: dict[str, Any] | None = None,
        limit: int = 0,
        skip: int = 0,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T] | list[ProjectionModel]:
        if projection_model:
            projection = self._get_projection_from_model(projection_model)
        else:
            projection = self._get_projection_from_model(self.default_model)
        query = self.__prepare_query__(query)
        pipeline = await self.prepare_pipeline(projection, query, limit, skip, sort)

        cursor: AsyncCursor[Any] | AsyncCommandCursor[Any]
        if pipeline:
            if MONGO_SETTINGS.mongo_explain:
                explanation = await self._database.command(
                    'aggregate', self.Meta.collection_name, pipeline=pipeline, explain=True
                )
                logger.debug(explanation)

            cursor = await self.collection.aggregate(pipeline=pipeline, session=session)
        else:
            mongo_sort = [(field, order.value) for field, order in sort.items()] if sort else None
            cursor = self.collection.find(
                filter=query,
                projection=projection,
                limit=limit,
                skip=skip,
                sort=mongo_sort,
                session=session,
            )

            if MONGO_SETTINGS.mongo_explain:
                explanation = await cursor.explain()
                logger.debug(explanation)

        if projection_model:
            return [
                projection_model.model_validate(
                    await self.prepare_object_data(data=doc, projection_model=projection_model)
                )
                for doc in await cursor.to_list()
            ]
        else:
            return [
                self.default_model.model_validate(
                    await self.prepare_object_data(data=doc, projection_model=self.default_model)
                )
                for doc in await cursor.to_list()
            ]

    async def count(
        self,
        query: dict[str, Any] | None = None,
        *,
        session: MongoAsyncClientSession | None = None,
        limit: int | None = None,
    ) -> int:
        query = self.__prepare_query__(query)
        projection = self._get_projection_from_model(EmptyModel)
        pipeline = await self.prepare_pipeline(projection, query)

        if pipeline:
            pipeline.append({'$count': 'count'})

            if limit is not None:
                pipeline.append({'$limit': limit})

            result = await (await self.collection.aggregate(pipeline=pipeline, session=session)).to_list()

            if not result:
                return 0

            return int(result[0]['count'])
        else:
            return await self.collection.count_documents(
                filter=query,
                session=session,
                **({'limit': limit} if limit else {}),
            )

    async def exists(
        self,
        query: dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> bool:
        return await self.count(query=query, session=session, limit=1) >= 1

    async def create(
        self,
        data: ModelType | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        prepared_data = await self.prepare_creation_data(data)

        try:
            result = await self.collection.insert_one(document=prepared_data, session=session)
        except MongoDuplicateKeyError as e:
            if e.details and 'keyValue' in e.details:
                raise DuplicateKeyException(key_value=e.details['keyValue']) from None
            raise DuplicateKeyException(str(e)) from None

        if not result.inserted_id:
            raise ObjectCreateException()

        return PyObjectId(result.inserted_id)

    async def bulk_create(
        self,
        data: list[ModelType] | list[dict[str, Any]],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> list[PyObjectId]:
        prepared_documents = []
        for item in data:
            prepared_documents.append(await self.prepare_creation_data(item))

        result = await self.collection.insert_many(documents=prepared_documents, session=session, ordered=False)

        return result.inserted_ids

    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId:
        try:
            data = await self.validate_object_data(data)
        except ValueError as e:
            raise ObjectUpdateException(str(e)) from e
        prepared_query = self.__prepare_query__(query)

        if isinstance(data, BaseModel):
            data = data.model_dump(exclude={'id'}, exclude_unset=exclude_unset)

        after_update_data = {}

        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            now = utc_now()
            for field in self.Meta.auto_now_fields:
                if operator == MongoUpdateOperator.set:
                    data[field] = now
                else:
                    after_update_data[field] = now

        document_count_to_update = await self.count(prepared_query)

        if document_count_to_update == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=prepared_query)
        elif document_count_to_update > 1:
            raise MultipleObjectsFoundException(obj_type=self.Meta.collection_name, query=prepared_query)

        result = await self.collection.find_one_and_update(
            filter=prepared_query,
            update={operator: data},
            upsert=False,
            return_document=ReturnDocument.AFTER,
            session=session,
            projection={'_id': 1},
        )
        result_id = PyObjectId(result['_id'])

        if result is None:
            raise ObjectUpdateException()

        if after_update_data:
            await self.collection.update_one(
                filter={'_id': result_id}, update={'$set': after_update_data}, session=session
            )

        return result_id

    async def bulk_update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        operator: MongoUpdateOperator = MongoUpdateOperator.set,
        session: MongoAsyncClientSession | None = None,
    ) -> list[PyObjectId]:
        try:
            data = await self.validate_object_data(data)
        except ValueError as e:
            raise ObjectUpdateException(str(e)) from e
        prepared_query = {'_id': query} if isinstance(query, PyObjectId) else query

        if isinstance(data, BaseModel):
            data = data.model_dump(exclude={'id'}, exclude_unset=exclude_unset)

        after_update_data = {}

        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            now = utc_now()
            for field in self.Meta.auto_now_fields:
                if operator == MongoUpdateOperator.set:
                    data[field] = now
                else:
                    after_update_data[field] = now

        documents_to_update = await self.get_list(query=prepared_query, session=session, projection_model=EmptyModel)
        documents_ids_to_update = [doc.id for doc in documents_to_update]

        await self.collection.update_many(
            filter={'_id': {'$in': documents_ids_to_update}},
            update={operator: data},
            upsert=False,
            session=session,
        )

        if after_update_data:
            await self.collection.update_one(
                filter={'_id': {'$in': documents_ids_to_update}}, update={'$set': after_update_data}, session=session
            )

        return documents_ids_to_update

    async def delete(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        query = self.__prepare_query__(query)
        count = await self.count(query=query, session=session)

        if count == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif count > 1:
            raise MultipleObjectsFoundException()

        result = await self.collection.delete_one(filter=query, session=session)
        return result.deleted_count

    async def delete_many(
        self,
        query: dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        query = self.__prepare_query__(query)
        result = await self.collection.delete_many(filter=query, session=session)
        return result.deleted_count

    async def aggregate(
        self,
        pipeline: list[dict],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> list:
        try:
            cursor = await self.collection.aggregate(pipeline=pipeline, session=session)
            return await cursor.to_list()
        except OperationFailure as e:
            msg = f'Error during pipeline execution in aggregate: {e}'
            raise MongoPipelineException(msg) from None

    async def _update_indexes(self) -> None:
        expected = dict(getattr(self.Meta, 'collection_index_to_keys', {}) or {})
        options = dict(getattr(self.Meta, 'collection_index_options', {}) or {})
        existing = await self.collection.index_information()
        existing_names = set(existing.keys())

        for idx_name in existing_names - {'_id_'}:
            if idx_name not in expected:
                try:
                    await self.collection.drop_index(idx_name)
                    logger.debug(f'Dropped unexpected index `{idx_name}`')
                except OperationFailure as e:
                    logger.warning(f'Cannot drop `{idx_name}`: {e}')

        for idx_name, keys in expected.items():
            if idx_name not in existing_names:
                idx_opts = options.get(idx_name, {})
                # Backward compatibility
                if 'unique' in idx_name.lower():
                    idx_opts['unique'] = True
                await self.collection.create_index(keys, name=idx_name, **idx_opts)
                logger.debug(f'Created index `{idx_name}`')

    async def create_collection(self) -> None:
        try:
            await self._database.create_collection(self.Meta.collection_name)
            logger.debug(f'Collection `{self.Meta.collection_name}` has been created')
        except CollectionInvalid:
            pass  # Collection already exists
        await self._update_indexes()
        await self._post_create_collection()

    async def _post_create_collection(self) -> None: ...


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
            return await self.get_list(
                query=query,
                limit=limit,
                skip=0,
                sort=sort,
                session=session,
                projection_model=projection_model,
            )
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
