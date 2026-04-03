from typing import Any

from saltbox_sdk.migrations.stages.mongo_base import MongoBaseMigrationStage


class MongoRenameCollectionStage(MongoBaseMigrationStage):
    def __init__(self, collection_name: str, new_collection_name: str):
        self.collection_name = collection_name
        self.new_collection_name = new_collection_name

    async def process(self) -> Any:
        mongo_client = self.mongo_client()
        mongo_collection = mongo_client.get_collection(self.collection_name)

        await mongo_collection.rename(new_name=self.new_collection_name)

        return f'Collection "{self.collection_name}" has been renamed to "{self.new_collection_name}".'


class MongoDropCollectionStage(MongoBaseMigrationStage):
    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    async def process(self) -> Any:
        mongo_client = self.mongo_client()
        mongo_collection = mongo_client.get_collection(self.collection_name)

        await mongo_collection.drop()

        return f'Collection "{self.collection_name}" has been dropped.'


class MongoCreateCollectionStage(MongoBaseMigrationStage):
    def __init__(self, collection_name: str):
        self.collection_name = collection_name

    async def process(self) -> Any:
        mongo_client = self.mongo_client()

        await mongo_client.create_collection(self.collection_name)

        return f'Collection "{self.collection_name}" has been created.'


class MongoDronIndexCollectionStage(MongoBaseMigrationStage):
    def __init__(self, collection_name: str, index_name: str):
        self.collection_name = collection_name
        self.index_name = index_name

    async def process(self) -> Any:
        mongo_client = self.mongo_client()
        mongo_collection = mongo_client.get_collection(self.collection_name)

        await mongo_collection.drop_index(self.index_name)

        return f'Index "{self.index_name}" has been dropped in collection "{self.collection_name}".'
