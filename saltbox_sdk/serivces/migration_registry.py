import importlib.util
import inspect
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any

import anyio

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.migration_schemas import BaseMigration


class LocalMigrationRegistry:
    """
    A static class for managing local migration scripts
    """
    @staticmethod
    async def get_sorted_migrations(
        root_path: anyio.Path,
        pattern_of_target_directory: str = '_migrations'
    ) -> list[BaseMigration]:
        migration_dirs = await LocalMigrationRegistry._extract_migration_dirs(root_path, pattern_of_target_directory)
        if not migration_dirs:
            logger.info('No migration directories found by root path: %s', pattern_of_target_directory)
            return []

        migrations: list[BaseMigration] = []
        for migration_dir in migration_dirs:
            logger.debug(f'Processing migration directory: {migration_dir}')
            migrations = await LocalMigrationRegistry._get_migration_instances(migration_dir)

        sorted_migrations = sorted(migrations, key=lambda m: m.id)
        logger.info(f'Loaded `{len(sorted_migrations)}` migrations')
        return sorted_migrations

    @staticmethod
    async def _get_migration_instances(path_to_dir: anyio.Path,) -> list[BaseMigration]:
        migrations: list[BaseMigration] = []
        async for file_path in path_to_dir.glob('*.py'):
            if file_path.name.startswith('__'):  # NOTE: skip __init__
                continue

            logger.debug(f'Loading migration file: {file_path}')
            module_type = await LocalMigrationRegistry._load_and_create_module_type(file_path)
            if module_type is None:
                continue

            migration_classes = await LocalMigrationRegistry._extract_migrations_from_module(module_type)
            for migration_class in migration_classes:
                migration_instance = await LocalMigrationRegistry._instantiate_migration(migration_class)
                migrations.append(migration_instance)
                logger.debug(f'Created migration instance: {migration_class.id}')

        return migrations


    @staticmethod
    async def _extract_migration_dirs(root_path: anyio.Path, pattern: str) -> list[anyio.Path]:
        path_to_target_dirs: list[anyio.Path] = []
        async for path in root_path.rglob(pattern):
            if await path.is_dir():
                path_to_target_dirs.append(path)
                logger.debug(f'Found migraiton directory: {path}')
        return path_to_target_dirs

    @staticmethod
    async def _load_and_create_module_type(file_path: anyio.Path) -> ModuleType | None:
        module_name = file_path.stem
        spec: ModuleSpec | None = importlib.util.spec_from_file_location(module_name, location=file_path)
        if spec is None or spec.loader is None:
            return None

        module_type = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module_type)
            logger.debug('Successfully loaded `{%s}` module', module_type.__name__)
            return module_type
        except Exception as exc:
            logger.warning(f'Failed to load migration module {file_path}: {exc}')
            return None

    @staticmethod
    async def _extract_migrations_from_module(module: Any) -> list[type[BaseMigration]]:
        migrations = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is not BaseMigration and issubclass(obj, BaseMigration) and not inspect.isabstract(obj):
                migrations.append(obj)
        return migrations

    @staticmethod
    async def _instantiate_migration(migration_class: type[BaseMigration]) -> BaseMigration:
        try:
            return migration_class()
        except Exception:
            logger.error(f'Failed to instantiate migration {migration_class.__name__}', stack_info=True)
            raise
