from datetime import UTC, datetime
from typing import get_args

import anyio
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.migration_schemas import BaseMigration, MigrationExecuteStatus, MigrationId, MigrationState
from saltbox_sdk.db.mongo.repository_base import BaseMongoRepository
from saltbox_sdk.db.mongo.schemas_base import SortOrder
from saltbox_sdk.db.redis.repository_sortedset_base import SortedsetRedisRepository  # noqa: F401
from saltbox_sdk.exceptions import DuplicateKeyException, MigrationDependencuNotAppliedException
from saltbox_sdk.serivces.migration_registry import LocalMigrationRegistry
from saltbox_sdk.serivces.mongo_base_service import MongoBaseService


class MigrationService(MongoBaseService[
    BaseMongoRepository[MigrationState],
    MigrationState,
    MigrationState,
    MigrationState
]):
    def __init__(self, repo: BaseMongoRepository[MigrationState], redis: Redis) -> None:
        self.redis = redis
        super().__init__(repo)

    async def execute_migrations(self, migration_root_path: anyio.Path) -> None:

        logger.info(f'Launching migrations by root path: {migration_root_path}')

        existing_local_migrations = await LocalMigrationRegistry.get_sorted_migrations(migration_root_path)
        applied_migration_ids: list[MigrationId] = await self._get_applied_ids()

        for migration in existing_local_migrations:
            logger.info(f'Try to execute `{migration.id}` migration')
            if migration.id in applied_migration_ids:
                logger.debug(f'Migration `{migration.id}` has already been applied. Skipping...')
                continue

            await self._validate_dependencies(migration, applied_migration_ids)
            await self._execute_migration(migration)
            applied_migration_ids.append(migration.id)


    async def _get_applied_ids(self) -> list[MigrationId]:
        records = await self.repo.get_list(
            query={'status': MigrationExecuteStatus.SUCCESS},
            limit=0,
            skip=0,
            sort={'id': SortOrder.ASC}
        )
        return [record.id for record in records]

    async def _validate_dependencies(self, migration: BaseMigration, applied_ids: list[MigrationId]) -> None:

        if not migration.dependencies:
            return

        logger.debug(f'Checking dependencies for {migration.id}: {migration.dependencies}')

        for dependency_id in migration.dependencies:
            if dependency_id not in applied_ids:
                msg = f'Migration `{migration.id}` requires `{dependency_id}` dependecny, but is not applied'
                raise MigrationDependencuNotAppliedException(msg)

    async def _execute_migration(self, migration: BaseMigration) -> None:
            try:
                logger.info(f'Executing `{migration.id}` migration')

                if self.is_migration_of(migration, AsyncDatabase):
                    await migration.action(self.repo.database)
                else:
                    await migration.action(self.redis)

                await self._mark_status(migration.id, MigrationExecuteStatus.SUCCESS)

                logger.info(f'Migration `{migration.id}` completed successfully')
            except Exception as exc:
                await self._handle_failed_migration(migration, exc)

    def is_migration_of(self, instance: BaseMigration, backend_type: type) -> bool:
        cls = type(instance)

        for base in getattr(cls, "__orig_bases__", []):
            (arg,) = get_args(base)
            return arg is backend_type

        return False

    async def _mark_status(
        self,
        migration_id: MigrationId,
        status: MigrationExecuteStatus = MigrationExecuteStatus.FAIL
    ) -> None:
        payload = {
            'id': migration_id,
            'status': status,
            'applied_at': datetime.now(tz=UTC)
        }
        existing = await self.repo.exists({'id': migration_id})
        if existing:
            _ = await self.repo.update({'id': migration_id}, payload, exclude_unset=False)
        else:
            _ = await self.repo.create(payload)

    async def _handle_failed_migration(self, migration: BaseMigration, exc: Exception) -> None:

        logger.exception(f'Migration `{migration.id}` failed: {exc}', stack_info=True)
        if isinstance(exc, DuplicateKeyException):
            raise

        try:
            await self._mark_status(migration.id, MigrationExecuteStatus.FAIL)
        except Exception:
            logger.error('Failed to mark migration status')
        raise
