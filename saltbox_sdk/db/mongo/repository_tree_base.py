from enum import Enum, auto
from typing import Any, ClassVar, overload

from pydantic import BaseModel
from pymongo import UpdateOne
from pymongo.asynchronous.client_session import AsyncClientSession as MongoAsyncClientSession

from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository, ModelType, ProjectionModel
from saltbox_sdk.db.mongo.schemas_base import PyObjectId, SortOrder
from saltbox_sdk.exceptions import (
    MultipleObjectsFoundException,
    ObjectDeleteException,
    ObjectNotFoundException,
    SaltBoxValidationException,
)
from saltbox_sdk.utilities.helpers import utc_now


class OnDelete(Enum):
    cascade = auto()
    protected = auto()


class BaseTreeMongoRepository[T: BaseModel](BaseMongoRepository[T]):
    class Meta(BaseMongoRepository.Meta):
        on_delete = OnDelete.protected
        parent_field_name: ClassVar[str] = 'parent_id'
        order_field_name: ClassVar[str | None] = None

    @staticmethod
    def _get_target_id(target: PyObjectId | ModelType) -> PyObjectId:
        if isinstance(target, PyObjectId):
            return target

        if hasattr(target, 'id') and isinstance(target.id, PyObjectId | str | bytes):
            return PyObjectId(target.id)

        msg = 'Target must be have "id" field'
        raise SaltBoxValidationException(msg)

    @overload
    async def get_children(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T]: ...

    @overload
    async def get_children(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel],
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ProjectionModel]: ...

    async def get_children(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
        projection_model: type[ProjectionModel] | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[T] | list[ProjectionModel]:
        query = {self.Meta.parent_field_name: self._get_target_id(target)}

        if projection_model is not None:
            result: list[ProjectionModel] = await self.get_list(
                query=query,
                limit=0,
                skip=0,
                session=session,
                projection_model=projection_model,
                sort=sort,
            )
            return result
        else:
            return await self.get_list(query=query, limit=0, skip=0, session=session, sort=sort)

    async def get_parent_id(
        self,
        target: PyObjectId | ModelType,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> PyObjectId | None:
        parent_field_name = self.Meta.parent_field_name

        if isinstance(target, BaseModel) and hasattr(target, parent_field_name):
            parent_id = getattr(target, parent_field_name)
            if parent_id is None or isinstance(parent_id, PyObjectId):
                return parent_id

            msg = f'Type of "{parent_field_name}" must be "PyObjectId"'
            raise SaltBoxValidationException(msg)

        query = {'_id': self._get_target_id(target)}
        obj_data = await self.collection.find(
            filter=query, projection={'_id': 1, parent_field_name: 1}, session=session
        ).to_list()

        if len(obj_data) == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif len(obj_data) > 1:
            raise MultipleObjectsFoundException()

        parent_id = obj_data[0].get(parent_field_name)
        return PyObjectId(parent_id) if parent_id is not None else None

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
        parent_id = await self.get_parent_id(target, session=session)

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
        parent_id_field_name: str | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> list[ProjectionModel]:
        parent_id_field_name = parent_id_field_name or self.Meta.parent_field_name
        nodes = await self.get_list(
            query=query, skip=0, limit=0, session=session, projection_model=projection_model, sort=sort
        )

        nodes_by_id: dict[Any, ProjectionModel] = {}
        for node in nodes:
            setattr(node, children_field_name, [])
            nodes_by_id[getattr(node, node_id_field_name)] = node

        tree: list[ProjectionModel] = []

        for node in nodes:
            parent = nodes_by_id.get(getattr(node, parent_id_field_name, None))
            if parent is None:
                tree.append(node)
            else:
                getattr(parent, children_field_name).append(node)

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
            ancestors_ids.append(self._get_target_id(target))

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

    async def get_descendants_ids(
        self,
        target: PyObjectId | ModelType,
        include_self: bool = False,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> list[PyObjectId]:
        """Get descendants ids list for target. If `include_self` is True, target id will be included.
        Descendants will be ordered level by level, from direct children to the deepest descendants.
        """
        target_id = self._get_target_id(target)
        descendants_ids: list[PyObjectId] = [target_id] if include_self else []
        level_ids = [target_id]

        while level_ids:
            children = await self.collection.find(
                filter={self.Meta.parent_field_name: {'$in': level_ids}}, projection={'_id': 1}, session=session
            ).to_list()
            level_ids = [PyObjectId(child['_id']) for child in children]
            descendants_ids.extend(level_ids)

        return descendants_ids

    async def validate_delete(
        self,
        ids: list[PyObjectId],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> None:
        pass

    async def delete(
        self,
        query: PyObjectId | dict[str, Any],
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> int:
        query = await self.__prepare_query__(query)
        find_result = await self.collection.find(filter=query, projection={'_id': 1}, session=session).to_list()

        if len(find_result) == 0:
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query=query)
        elif len(find_result) > 1:
            raise MultipleObjectsFoundException()

        target_id = PyObjectId(find_result[0]['_id'])

        if self.Meta.on_delete == OnDelete.protected:
            if await self.exists({self.Meta.parent_field_name: target_id}, session=session):
                raise ObjectDeleteException(detail='The object cannot be deleted because it has child elements')
            ids = [target_id]
        else:
            ids = await self.get_descendants_ids(target_id, include_self=True, session=session)

        await self.validate_delete(ids, session=session)

        result = await self.collection.delete_many(filter={'_id': {'$in': ids}}, session=session)
        return result.deleted_count

    async def validate_move(
        self,
        target_id: PyObjectId,
        parent_id: PyObjectId | None,
        *,
        session: MongoAsyncClientSession | None = None,
    ) -> None:
        pass

    async def move(
        self,
        target_id: PyObjectId,
        parent_id: PyObjectId | None,
        insert_before_id: PyObjectId | None = None,
        *,
        session: MongoAsyncClientSession | None = None,
        sort: dict[str, SortOrder] | None = None,
    ) -> PyObjectId:
        parent_field_name = self.Meta.parent_field_name
        order_field_name = self.Meta.order_field_name

        if parent_id == target_id:
            msg = 'Cannot move node into itself'
            raise SaltBoxValidationException(msg)

        if not await self.exists({'_id': target_id}, session=session):
            raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query={'_id': target_id})

        if parent_id is not None:
            if not await self.exists({'_id': parent_id}, session=session):
                raise ObjectNotFoundException(obj_type=self.Meta.collection_name, query={'_id': parent_id})

            if parent_id in await self.get_descendants_ids(target_id, session=session):
                msg = 'Cannot move node into its own descendant'
                raise SaltBoxValidationException(msg)

        await self.validate_move(target_id, parent_id, session=session)

        target_update: dict[str, Any] = {parent_field_name: parent_id}
        if hasattr(self.Meta, 'auto_now_fields') and self.Meta.auto_now_fields:
            now = utc_now()
            target_update.update(dict.fromkeys(self.Meta.auto_now_fields, now))

        operations = [UpdateOne({'_id': target_id}, {'$set': target_update})]

        if order_field_name is not None:
            siblings_sort = sort or {order_field_name: SortOrder.ASC}
            siblings = await self.collection.find(
                filter={parent_field_name: parent_id, '_id': {'$ne': target_id}},
                projection={'_id': 1},
                sort=[(field, order.value) for field, order in siblings_sort.items()],
                session=session,
            ).to_list()
            ordered_ids = [PyObjectId(sibling['_id']) for sibling in siblings]

            try:
                insert_at = ordered_ids.index(insert_before_id) if insert_before_id else len(ordered_ids)
            except ValueError:
                insert_at = len(ordered_ids)

            ordered_ids.insert(insert_at, target_id)
            operations.extend(
                UpdateOne({'_id': node_id}, {'$set': {order_field_name: order}})
                for order, node_id in enumerate(ordered_ids, start=1)
            )

        await self.collection.bulk_write(operations, session=session)

        return target_id
