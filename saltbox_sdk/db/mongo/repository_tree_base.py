from enum import Enum, auto
from typing import Any, overload

from pydantic import BaseModel
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession

from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, ModelType, ProjectionModel
from saltbox_sdk.db.mongo.schemas_base import BaseTreeModel, PyObjectId
from saltbox_sdk.exceptions import (
    MultipleObjectsFoundException,
    ObjectDeleteException,
    ObjectNotFoundException,
    SaltBoxValidationException,
)


class OnDelete(Enum):
    cascade = auto()
    protected = auto()


class BaseTreeMongoRepository[T: BaseModel](BaseMongoRepository[T]):
    class Meta(BaseMongoRepository.Meta):
        on_delete = OnDelete.protected

    @overload
    async def get_children(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> list[T]: ...

    @overload
    async def get_children(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> list[ProjectionModel]: ...

    async def get_children(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> list[T] | list[ProjectionModel]:
        if isinstance(target, BaseModel):
            if hasattr(target, 'id'):
                target_id = target.id
            else:
                msg = 'Target must be have "id" field"'
                raise SaltBoxValidationException(msg)
        elif isinstance(target, PyObjectId):
            target_id = target
        else:
            msg = 'Unknown target type'  # type: ignore
            raise SaltBoxValidationException(msg)

        if projection_model is not None:
            return await self.get_list(
                query={'parent_id': target_id}, session=session, projection_model=projection_model, limit=0, skip=0
            )
        else:
            return await self.get_list(query={'parent_id': target_id}, session=session, limit=0, skip=0)

    async def get_parent_id(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId | None:
        if isinstance(target, BaseModel):
            if hasattr(target, 'parent_id'):
                if isinstance(target.parent_id, PyObjectId):
                    return target.parent_id

                msg = 'Type of "parent_id" must be "PyObjectId"'
                raise SaltBoxValidationException(msg)

            if hasattr(target, 'id'):
                return await self.get_parent_id(PyObjectId(target.id))

            msg = 'Target must be have "id" field'
            raise SaltBoxValidationException(msg)

        elif isinstance(target, PyObjectId):
            query = {'_id': target}
            obj_data = await self.collection.find(
                filter=query, projection={'_id': 1, 'parent_id': 1}, session=session
            ).to_list()

            if len(obj_data) == 0:
                raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
            elif len(obj_data) > 1:
                raise MultipleObjectsFoundException()

            return PyObjectId(obj_data[0]['parent_id']) if 'parent_id' in obj_data[0] else None
        else:
            msg = 'Unknown target type'  # type: ignore
            raise SaltBoxValidationException(msg)

    @overload
    async def get_parent(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> T | None: ...

    @overload
    async def get_parent(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
    ) -> ProjectionModel | None: ...

    async def get_parent(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
    ) -> T | ProjectionModel | None:
        parent_id = await self.get_parent_id(target)

        if parent_id is None:
            return None

        try:
            if projection_model is not None:
                return await self.get(query=parent_id, projection_model=projection_model, session=session)
            else:
                return await self.get(query=parent_id, session=session)
        except ObjectNotFoundException:
            return None

    async def delete(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        query = self.__prepare_query__(query)
        projection = self._get_projection_from_model(BaseTreeModel)
        deleted_count = 0

        find_result = await self.collection.find(filter=query, projection=projection, session=session).to_list()

        if len(find_result) == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif len(find_result) > 1:
            raise MultipleObjectsFoundException()

        obj = BaseTreeModel.model_validate(find_result[0])

        if self.Meta.on_delete == OnDelete.protected:
            if self.exists({'parent_id': obj.id}):
                raise ObjectDeleteException(detail='The object cannot be deleted because it has child elements')
        elif self.Meta.on_delete == OnDelete.cascade:
            for child in await self.get_children(target=obj, projection_model=BaseTreeModel, session=session):
                deleted_count += await self.delete(query=child.id, session=session)

        result = await self.collection.delete_one(filter=query, session=session)
        deleted_count += result.deleted_count
        return deleted_count
