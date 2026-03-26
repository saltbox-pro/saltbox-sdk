from typing import Any, ClassVar

from pymongo.asynchronous.database import AsyncDatabase as MongoAsyncDatabase

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.mongo.config import get_mongo_db
from saltbox_sdk.migrations.exceptions import MigrationError
from saltbox_sdk.migrations.repositories.migration import MigrationRepository, get_migration_repository
from saltbox_sdk.migrations.schemas.migration import MigrationCreateSchema, MigrationStatus
from saltbox_sdk.migrations.services.migration import MigrationService, get_migration_service
from saltbox_sdk.migrations.stages.base import BaseMigrationStage


class BaseMigration:
    dependencies: ClassVar[list[str]] = []
    stages: ClassVar[list[BaseMigrationStage]] = []
    _mongo_client: MongoAsyncDatabase | None = None
    _migration_repository: MigrationRepository | None = None
    _migration_service: MigrationService | None = None

    @property
    def migration_name(self) -> str:
        return self.__module__

    def mongo_client(self) -> MongoAsyncDatabase:
        if self._mongo_client is None:
            self._mongo_client = get_mongo_db()

        return self._mongo_client

    def migration_service(self) -> MigrationService:
        if self._migration_repository is None:
            self._migration_repository = get_migration_repository(db=self.mongo_client())

        if self._migration_service is None:
            self._migration_service = get_migration_service(repo=self._migration_repository)

        return self._migration_service

    async def run_migration(self) -> None:
        service = self.migration_service()
        stages_results: list[Any] = []
        error = None

        if await service.exists(query={'name': self.migration_name, 'status': MigrationStatus.success}):
            logger.info(f'Migration {self.migration_name} has already been successfully completed earlier')
            return

        for stage in self.stages:
            try:
                stages_results.append(await stage.process())
            except Exception as exc:
                stages_results.append(str(exc))
                error = exc
                break

        await service.create(
            data=MigrationCreateSchema.model_validate(
                {
                    'name': self.migration_name,
                    'status': MigrationStatus.success if error is None else MigrationStatus.failed,
                    'stages_results': stages_results,
                }
            )
        )

        if error:
            msg = f'Migration {self.migration_name} has failed:\r\n{error!s}'
            raise MigrationError(msg) from error

        logger.info(
            f'Migration {self.migration_name} has been successfully completed:\r\n'
            f'{"\r\n".join([f"\t - {stage_result}" for stage_result in stages_results])}'
        )
