from typing import Annotated

from fastapi import Depends

from saltbox_sdk.migrations.repositories.migration import MigrationRepository, get_migration_repository
from saltbox_sdk.migrations.schemas.migration import MigrationCreateSchema, MigrationModel, MigrationUpdateSchema
from saltbox_sdk.serivces.mongo_base_service import MongoBaseService


class MigrationService(
    MongoBaseService[MigrationRepository, MigrationModel, MigrationCreateSchema, MigrationUpdateSchema]
): ...


def get_migration_service(
    repo: Annotated[MigrationRepository, Depends(get_migration_repository)],
) -> MigrationService:
    return MigrationService(repo)
