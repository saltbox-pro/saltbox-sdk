from typing import Any

from saltbox_sdk.migrations.exceptions import MigrationError
from saltbox_sdk.migrations.stages.mongo_base import MongoBaseMigrationStage


class MongoSetFieldStage(MongoBaseMigrationStage):
    def __init__(self, collection_name: str, field_name: str, value: Any, mongo_filter: dict | None = None):
        self.collection_name = collection_name
        self.field_name = field_name
        self.value = value
        self.mongo_filter = mongo_filter or {}

    async def process(self) -> Any:
        mongo_client = self.mongo_client()
        mongo_collection = mongo_client.get_collection(self.collection_name)

        if callable(self.value):
            value = f'(from {self.value.__name__})'

            modified_count = 0
            matched_count = await mongo_collection.count_documents(filter=self.mongo_filter)

            find_result = mongo_collection.find(filter=self.mongo_filter)

            for document in await find_result.to_list():
                try:
                    document_id = document['_id']
                except KeyError as e:
                    msg = 'Only documents with "_id" fields are supported for callable values.'
                    raise MigrationError(msg) from e

                await mongo_collection.update_one(
                    filter={'_id': document_id},
                    update={'$set': {self.field_name: self.value(document)}},
                )

                modified_count += 1
        else:
            value = self.value

            result = await mongo_collection.update_many(
                filter=self.mongo_filter, update={'$set': {self.field_name: value}}
            )
            modified_count = result.modified_count
            matched_count = result.matched_count

        return self._get_result(modified_count=modified_count, matched_count=matched_count, value=value)

    def _get_result(self, modified_count: int, matched_count: int, value: Any) -> str:
        return (
            f'Field "{self.field_name}" has been set to "{value}" in collection "{self.collection_name}". '
            f'{modified_count} documents have been changed. There are a total of {matched_count} documents in the '
            f'collection that matched by filter.'
        )


class MongoAddFieldStage(MongoSetFieldStage):
    def __init__(self, collection_name: str, field_name: str, value: Any, mongo_filter: dict | None = None):
        super().__init__(collection_name=collection_name, field_name=field_name, value=value, mongo_filter=mongo_filter)

        self.mongo_filter = {
            '$and': [
                self.mongo_filter,
                {self.field_name: {'$exists': False}},
            ],
        }

    def _get_result(self, modified_count: int, matched_count: int, value: Any) -> str:
        return (
            f'Field "{self.field_name}" has been added with value "{value}" in collection "{self.collection_name}". '
            f'{modified_count} documents have been changed. There are a total of {matched_count} documents in the '
            f'collection that matched by filter.'
        )


class MongoUpdateFieldStage(MongoSetFieldStage):
    def __init__(self, collection_name: str, field_name: str, value: Any, mongo_filter: dict | None = None):
        super().__init__(collection_name=collection_name, field_name=field_name, value=value, mongo_filter=mongo_filter)

        self.mongo_filter = {
            '$and': [
                self.mongo_filter,
                {self.field_name: {'$exists': True}},
            ],
        }

    def _get_result(self, modified_count: int, matched_count: int, value: Any) -> str:
        return (
            f'Field "{self.field_name}" has been updated to value "{value}" in collection "{self.collection_name}". '
            f'{modified_count} documents have been changed. There are a total of {matched_count} documents in the '
            f'collection that matched by filter.'
        )


class MongoRenameFieldStage(MongoBaseMigrationStage):
    def __init__(
        self, collection_name: str, field_name_old: str, field_name_new: str, *, mongo_filter: dict | None = None
    ):
        self.collection_name = collection_name
        self.field_name_old = field_name_old
        self.field_name_new = field_name_new
        self.mongo_filter = mongo_filter or {}

    async def process(self) -> Any:
        mongo_client = self.mongo_client()
        mongo_collection = mongo_client.get_collection(self.collection_name)

        result = await mongo_collection.update_many(
            filter=self.mongo_filter, update={'$rename': {self.field_name_old: self.field_name_new}}
        )

        return (
            f'Field "{self.field_name_old}" has been renamed to "{self.field_name_new}" in collection '
            f'"{self.collection_name}". {result.modified_count} documents have been changed. There are a total of '
            f'{result.matched_count} documents in the collection that matched by filter.'
        )


class MongoRemoveFieldStage(MongoBaseMigrationStage):
    def __init__(self, collection_name: str, field_name: str, *, mongo_filter: dict | None = None):
        self.collection_name = collection_name
        self.field_name = field_name
        self.mongo_filter = mongo_filter or {}

    async def process(self) -> Any:
        mongo_client = self.mongo_client()
        mongo_collection = mongo_client.get_collection(self.collection_name)

        result = await mongo_collection.update_many(filter=self.mongo_filter, update={'$unset': {self.field_name: ''}})

        return (
            f'Field "{self.field_name}" has been removed from collection "{self.collection_name}". '
            f'{result.modified_count} documents have been changed. There are a total of {result.matched_count} '
            f'documents in the collection that matched by filter.'
        )
