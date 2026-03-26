import abc

from pymongo.asynchronous.database import AsyncDatabase as MongoAsyncDatabase

from saltbox_sdk.db.mongo.config import get_mongo_db
from saltbox_sdk.migrations.stages.base import BaseMigrationStage


class MigrationMongoMixin:
    _mongo_client: MongoAsyncDatabase | None = None

    def mongo_client(self) -> MongoAsyncDatabase:
        if self._mongo_client is None:
            self._mongo_client = get_mongo_db()

        return self._mongo_client


class MongoBaseMigrationStage(BaseMigrationStage, MigrationMongoMixin, abc.ABC): ...
