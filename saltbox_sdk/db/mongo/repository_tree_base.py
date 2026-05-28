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

        if projection_model is not None:
            result: list[ProjectionModel] = await self.get_list(
                query={'parent_id': target_id}, session=session, projection_model=projection_model, limit=0, skip=0
            )
            return result
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

            if hasattr(target, 'id') and isinstance(target.id, PyObjectId | str | bytes | type(None)):
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

    async def get_tree(
        self,
        query: dict[str, Any] | None = None,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
        children_field_name: str = 'children',
        node_id_field_name: str = 'id',
        parent_id_field_name: str = 'parent_id',
    ) -> list[ProjectionModel]:
        nodes = await self.get_list(query=query, skip=0, limit=0, session=session, projection_model=projection_model)
        nodes_id = [getattr(node, node_id_field_name) for node in nodes]
        tree: list[ProjectionModel] = []

        def add_node_recursive(new_node: ProjectionModel, parent_node: ProjectionModel) -> bool:
            if getattr(parent_node, node_id_field_name) == getattr(new_node, parent_id_field_name):
                getattr(parent_node, children_field_name).append(new_node)
                return True

            for child_node in getattr(parent_node, children_field_name, []):
                if add_node_recursive(new_node, child_node):
                    return True

            return False

        while len(nodes) > 0:
            node = nodes.pop(0)

            if getattr(node, parent_id_field_name, None) not in nodes_id:
                tree.append(node)
                continue

            for tree_node in tree:
                if add_node_recursive(node, tree_node):
                    break

                nodes.append(node)

        return tree

    async def get_ancestors_ids(
        self,
        target: PyObjectId | ModelType,
        include_self: bool = False,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> list[PyObjectId]:
        """Get ancestors ids list for target. If `include_self` is True, target id will be included.
        Ancestors will be ordered from root to direct parent (and to target if `include_self` is True).
        """
        ancestors_ids: list[PyObjectId] = []
        if include_self:
            if isinstance(target, BaseModel):
                if hasattr(target, 'id') and isinstance(target.id, PyObjectId | str | bytes | type(None)):
                    ancestors_ids.append(PyObjectId(target.id))
                else:
                    msg = 'Target must be have "id" field"'
                    raise SaltBoxValidationException(msg)
            elif isinstance(target, PyObjectId):
                ancestors_ids.append(target)

        try:
            parent_id = await self.get_parent_id(target, session=session)
        except ObjectNotFoundException:
            return ancestors_ids

        while parent_id is not None:
            ancestors_ids.insert(0, parent_id)
            try:
                parent_id = await self.get_parent_id(parent_id, session=session)
            except ObjectNotFoundException:
                break

        return ancestors_ids

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
            if await self.exists({'parent_id': obj.id}, session=session):
                raise ObjectDeleteException(detail='The object cannot be deleted because it has child elements')
        elif self.Meta.on_delete == OnDelete.cascade:
            for child in await self.get_children(target=obj, projection_model=BaseTreeModel, session=session):
                deleted_count += await self.delete(query=child.id, session=session)

        result = await self.collection.delete_one(filter=query, session=session)
        deleted_count += result.deleted_count
        return deleted_count
