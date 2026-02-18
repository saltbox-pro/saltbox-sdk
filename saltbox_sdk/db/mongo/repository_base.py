import re
from collections.abc import Callable
from inspect import isclass
from typing import Any, ClassVar, TypeVar, cast, overload

from pydantic import BaseModel
from pymongo.asynchronous.client_session import (
    AsyncClientSession as MongoAsyncClientSession,
)
from pymongo.asynchronous.collection import AsyncCollection, ReturnDocument
from pymongo.asynchronous.command_cursor import AsyncCommandCursor
from pymongo.asynchronous.cursor import AsyncCursor
from pymongo.asynchronous.database import AsyncDatabase as MongoAsyncDatabase
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
from pymongo.errors import OperationFailure
from pymongo.operations import _IndexKeyHint  # pyright: ignore[reportPrivateUsage]

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.abc_repository import AbstractRepository
from saltbox_sdk.db.mongo.aggregations import AggregationsStore
from saltbox_sdk.db.mongo.schemas_base import PyObjectId, SortOrder
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


class BaseMongoRepository[T: BaseModel](AbstractRepository[T]):
    class Meta:
        collection_name: ClassVar[str]
        auto_now_add_fields: ClassVar[list[str]]
        auto_now_fields: ClassVar[list[str]]
        query_overrides: ClassVar[dict[str, str]]
        aggregations: ClassVar[AggregationsStore] = AggregationsStore()
        collection_index_to_keys: ClassVar[dict[str, _IndexKeyHint]]

    def __init__(self, database: MongoAsyncDatabase[Any], **kwargs: Any) -> None:
        super().__init__()
        self.__database: MongoAsyncDatabase[Any] = database
        self.__validate()

    @property
    def client(self) -> AsyncMongoClient[Any]:
        return self.__database.client

    @property
    def collection(self) -> AsyncCollection[Any]:
        return self.__database[self.Meta.collection_name]

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
                    if isinstance(data_value, dict):
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
        return self.aggregations.build_pipeline(fields_names=list(projection.keys()))

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
            result = await (await self.collection.aggregate(pipeline=pipeline, session=session)).to_list()
        else:
            result = await self.collection.find(filter=query, projection=projection, session=session).to_list()

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
        limit: int,
        skip: int,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T]: ...

    @overload
    async def get_list(
        self,
        query: dict[str, Any] | None,
        limit: int,
        skip: int,
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

        result: AsyncCursor[Any] | AsyncCommandCursor[Any]
        if pipeline:
            result = await self.collection.aggregate(pipeline=pipeline, session=session)
        else:
            mongo_sort = [(field, order.value) for field, order in sort.items()] if sort else None
            result = self.collection.find(
                filter=query,
                projection=projection,
                limit=limit,
                skip=skip,
                sort=mongo_sort,
                session=session,
            )

        if projection_model:
            return [
                projection_model.model_validate(
                    await self.prepare_object_data(data=doc, projection_model=projection_model)
                )
                for doc in await result.to_list()
            ]
        else:
            return [
                self.default_model.model_validate(
                    await self.prepare_object_data(data=doc, projection_model=self.default_model)
                )
                for doc in await result.to_list()
            ]

    async def count(
        self,
        query: dict[str, Any] | None = None,
        *,
        session: MongoAsyncClientSession | None = None,
        limit: int | None = None,
    ) -> int:
        query = self.__prepare_query__(query)
        projection = self._get_projection_from_model(self.default_model)
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

    @overload
    async def create(
        self,
        data: ModelType | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> T: ...

    @overload
    async def create(
        self,
        data: ModelType | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def create(  # noqa: C901
        self,
        data: ModelType | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> T | ProjectionModel:
        try:
            data = await self.validate_object_data(data)
        except ValueError as e:
            raise ObjectCreateException(str(e)) from e

        if isinstance(data, BaseModel):
            data = data.model_dump(exclude={'id'})  # probably don't need to exclude id

        now = utc_now()
        if hasattr(self.Meta, 'auto_now_add_fields') and self.Meta.auto_now_add_fields:
            for field in self.Meta.auto_now_add_fields:
                data[field] = now
        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                data[field] = now

        try:
            result = await self.collection.insert_one(document=data, session=session)
        except MongoDuplicateKeyError as e:
            if e.details and 'keyValue' in e.details:
                raise DuplicateKeyException(key_value=e.details['keyValue']) from None
            raise DuplicateKeyException(str(e)) from None

        if not result.inserted_id:
            raise ObjectCreateException()

        if projection_model:
            return await self.get(
                PyObjectId(result.inserted_id),
                session=session,
                projection_model=projection_model,
            )
        else:
            return await self.get(PyObjectId(result.inserted_id), session=session)

    @overload
    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> T: ...

    @overload
    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> T | ProjectionModel:
        try:
            data = await self.validate_object_data(data)
        except ValueError as e:
            raise ObjectUpdateException(str(e)) from e
        query = self.__prepare_query__(query)

        if isinstance(data, BaseModel):
            data = data.model_dump(exclude={'id'}, exclude_unset=exclude_unset)

        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            now = utc_now()
            for field in self.Meta.auto_now_fields:
                data[field] = now
        if not await self.exists(query):
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)

        # TODO (a.karmanov): FIXME What if query matches multiple? May be UpdateMany is more appropriate?
        result = await self.collection.find_one_and_update(
            filter=query,
            update={'$set': data},
            upsert=False,
            return_document=ReturnDocument.AFTER,
            session=session,
            projection={'_id': 1},
        )

        if result is None:
            raise ObjectUpdateException()

        if projection_model:
            return await self.get(
                PyObjectId(result['_id']),
                session=session,
                projection_model=projection_model,
            )
        else:
            return await self.get(PyObjectId(result['_id']), session=session)

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

    async def create_collection(self) -> None:
        collection_name = self.__class__.__name__
        indexes: dict[str, _IndexKeyHint] = self.Meta.collection_index_to_keys

        if not indexes:
            await self._post_create_collection()
            return

        msg = f'Try to create `{collection_name}`'
        logger.debug(msg)

        msg = f'Expected indexes in `{collection_name}`: {list(indexes.keys())}'
        logger.debug(msg)

        existing_indexes = sorted(await self.collection.index_information())
        msg = f'Existing indexes from `{collection_name}`: {existing_indexes}'
        logger.debug(msg)

        created = 0
        for expected_index, keys in indexes.items():
            if expected_index not in existing_indexes:
                _ = await self.collection.create_index(
                    keys, name=expected_index, unique=bool(re.search('unique', expected_index))
                )
                created += 1
                msg = f'Missing `{expected_index}` index has been created'
                logger.debug(msg)

        if not created:
            msg = f'`{collection_name}` already exists.'
            logger.debug(msg)

        await self._post_create_collection()

    async def _post_create_collection(self) -> None: ...
