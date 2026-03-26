from typing import Annotated, ClassVar

from fastapi import Depends
from pymongo.asynchronous.database import AsyncDatabase

from saltbox_sdk.db.mongo.config import get_mongo
from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository
from saltbox_sdk.migrations.schemas.migration import MigrationModel


class MigrationRepository(BaseMongoRepository[MigrationModel]):
    class Meta:
        collection_name = '__migrations__'
        auto_now_add_fields: ClassVar[list[str]] = ['created']
        auto_now_fields: ClassVar[list[str]] = ['modified']


def get_migration_repository(db: Annotated[AsyncDatabase, Depends(get_mongo)]) -> MigrationRepository:
    return MigrationRepository(db)
