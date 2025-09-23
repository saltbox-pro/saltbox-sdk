from collections.abc import Callable
from inspect import isclass
from typing import Any, ClassVar, TypeVar, cast, overload

from pydantic import BaseModel
from pymongo.asynchronous.collection import AsyncCollection
from pymongo.errors import DuplicateKeyError as MongoDuplicateKeyError
from pymongo.errors import OperationFailure

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.abc_repository import AbstractRepository
from saltbox_sdk.db.mongo import MongoAsyncDatabase
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

    def __init__(self, database: MongoAsyncDatabase):
        super().__init__()
        self.__database: MongoAsyncDatabase = database
        self.__validate()

    @property
    def __query_overrides__(self) -> dict[str, Callable]:
        query_overrides = {}

        if hasattr(self.Meta, 'query_overrides') and self.Meta.query_overrides:
            for override_name, override_callback_name in self.Meta.query_overrides.items():
                query_overrides[override_name] = getattr(self, override_callback_name)

        return query_overrides

    def __prepare_query__(self, query: PyObjectId | dict[str, Any] | None) -> dict[str, Any]:
        if isinstance(query, PyObjectId):
            return {'_id': query}

        if query is None:
            return {}

        query_overrides = self.__query_overrides__

        def recursive_override(data: dict[str, Any]) -> dict[str, Any]:
            query: dict[str, Any] = {}

            for data_key, data_value in data.items():
                if data_key in query_overrides.keys():
                    override_key, override_value = query_overrides[data_key](data_key, data_value)
                    if override_value is not None:
                        query[override_key] = override_value
                else:
                    if isinstance(data_value, dict):
                        query[data_key] = recursive_override(data_value)
                    # TODO (i.moshkov): check if this is correct
                    elif isinstance(data_value, list) and data_key not in ['$in', '$nin']:
                        query[data_key] = [recursive_override(item_value) for item_value in data_value]
                    else:
                        try:
                            query['$or'] = [{data_key: data_value}, {data_key: PyObjectId(data_value)}]
                        except Exception:
                            query[data_key] = data_value
            return query

        query = recursive_override(query)

        return cast(dict[str, Any], recursive_replace_dates(query))

    async def prepare_object_data(self, data: dict[str, Any]) -> dict[str, Any]:
        return data

    @overload
    async def validate_object_data(self, data: ModelType) -> ModelType: ...

    @overload
    async def validate_object_data(self, data: dict[str, Any]) -> dict[str, Any]: ...

    async def validate_object_data(self, data: ModelType | dict[str, Any]) -> ModelType | dict[str, Any]:
        return data

    @property
    def collection(self) -> AsyncCollection:
        return self.__database[self.Meta.collection_name]

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
                    raise SaltBoxValidationException(msg.format(field, self.Meta.collection_name))
        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            for field in self.Meta.auto_now_fields:
                if field not in self.default_model.model_fields:
                    msg = f'Meta `auto_now_fields` `{field}` should be in model fields'
                    raise SaltBoxValidationException(msg.format(field, self.Meta.collection_name))

    @staticmethod
    def _get_projection_from_model(model: type[ProjectionModel]) -> dict[str, Any]:
        projection = {}
        for field_name, field in model.model_fields.items():
            if field.annotation and isclass(field.annotation) and issubclass(field.annotation, BaseModel):
                sub_model = field.annotation
                for sub_field_name in sub_model.model_fields:
                    projection[f'{field_name}.{sub_field_name}'] = 1
            else:
                projection[field_name] = 1

        return projection

    @overload
    async def get(self, query: PyObjectId | dict[str, Any]) -> T: ...

    @overload
    async def get(
        self, query: PyObjectId | dict[str, Any], projection_model: type[ProjectionModel]
    ) -> ProjectionModel: ...

    async def get(
        self, query: PyObjectId | dict[str, Any], projection_model: type[ProjectionModel] | None = None
    ) -> ProjectionModel | T:
        projection = self._get_projection_from_model(projection_model) if projection_model else None

        query = self.__prepare_query__(query)
        result = await self.collection.find(filter=query, projection=projection).to_list()

        if len(result) == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif len(result) > 1:
            raise MultipleObjectsFoundException()

        data = await self.prepare_object_data(result[0])

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
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T]: ...

    @overload
    async def get_list(
        self,
        query: dict[str, Any] | None,
        limit: int,
        skip: int,
        projection_model: type[ProjectionModel],
        *,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ProjectionModel]: ...

    async def get_list(
        self,
        query: dict[str, Any] | None = None,
        limit: int = 0,
        skip: int = 0,
        projection_model: type[ProjectionModel] | None = None,
        *,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T] | list[ProjectionModel]:
        projection = self._get_projection_from_model(projection_model) if projection_model else None
        query = self.__prepare_query__(query)
        mongo_sort = [(field, order.value) for field, order in sort.items()] if sort else None
        result = self.collection.find(filter=query, projection=projection, limit=limit, skip=skip, sort=mongo_sort)

        if projection_model:
            return [
                projection_model.model_validate(await self.prepare_object_data(doc)) for doc in await result.to_list()
            ]
            # return [projection_model.model_validate(doc) async for doc in result]
        else:
            return [
                self.default_model.model_validate(await self.prepare_object_data(doc)) for doc in await result.to_list()
            ]

    async def count(self, query: dict[str, Any] | None = None) -> int:
        query = self.__prepare_query__(query)
        return await self.collection.count_documents(query)

    async def exists(self, query: dict[str, Any]) -> bool:
        query = self.__prepare_query__(query)
        return await self.collection.count_documents(query, limit=1) == 1

    @overload
    async def create(self, data: ModelType | dict[str, Any]) -> T: ...

    @overload
    async def create(
        self, data: ModelType | dict[str, Any], projection_model: type[ProjectionModel]
    ) -> ProjectionModel: ...

    async def create(  # noqa: C901
        self,
        data: ModelType | dict[str, Any],
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
            result = await self.collection.insert_one(data)
        except MongoDuplicateKeyError as e:
            logger.debug(f'{type(e.details)}')
            if e.details and 'keyValue' in e.details:
                raise DuplicateKeyException(key_value=e.details['keyValue']) from None
            raise DuplicateKeyException(str(e)) from None

        if not result.inserted_id:
            raise ObjectCreateException()

        if projection_model:
            return await self.get(PyObjectId(result.inserted_id), projection_model=projection_model)
        else:
            return await self.get(PyObjectId(result.inserted_id))

    @overload
    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
    ) -> T: ...

    @overload
    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
        *,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel: ...

    async def update(
        self,
        query: PyObjectId | dict[str, Any],
        data: ModelType | dict[str, Any],
        exclude_unset: bool = True,
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
        result = await self.collection.update_one(query, {'$set': data}, upsert=False)
        if result.modified_count == 0:
            raise ObjectUpdateException()

        if projection_model:
            return await self.get(query, projection_model=projection_model)
        else:
            return await self.get(query)

    async def delete(self, query: PyObjectId | dict[str, Any]) -> int:
        query = self.__prepare_query__(query)
        count = await self.count(query)

        if count == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif count > 1:
            raise MultipleObjectsFoundException()

        result = await self.collection.delete_one(query)
        return result.deleted_count

    async def delete_many(self, query: dict[str, Any]) -> int:
        query = self.__prepare_query__(query)
        result = await self.collection.delete_many(query)
        return result.deleted_count

    async def aggregate(self, pipeline: list[dict]) -> list:
        try:
            cursor = await self.collection.aggregate(pipeline)
            return await cursor.to_list()
        except OperationFailure as e:
            msg = f'Error during pipeline execution in aggregate: {e}'
            raise MongoPipelineException(msg) from None
