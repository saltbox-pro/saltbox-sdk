from importlib import import_module
from pkgutil import iter_modules

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.migrations.base_migration import BaseMigration
from saltbox_sdk.migrations.exceptions import MigrationError


class Migrator:
    _modules_paths: list[list[str]]
    _migrations: dict[str, type[BaseMigration]]

    def __init__(self, modules_paths: list[list[str]]) -> None:
        self._modules_paths = modules_paths

    def _import_migrations(self) -> None:
        self._migrations = {}

        for module_path in self._modules_paths:
            for _, name, _ in iter_modules([f'./{"/".join(module_path)}/migrations']):
                import_module(f'{".".join(module_path)}.migrations.{name}')

        for migration in BaseMigration.__subclasses__():
            if migration.__module__ in self._migrations.keys():
                msg = f'Migration {migration.__module__} has more than one migration class'
                raise MigrationError(msg)

            self._migrations[migration.__module__] = migration

    # TODO (@): check migrations for correct dependencies, using our repositories, services and other
    def _check_migrations(self) -> None: ...

    def _prepare_migrations_queue(self) -> list[str]:
        migrations_names_stack = sorted(self._migrations.keys())
        migrations_names: list[str] = []

        while len(migrations_names_stack):
            migration_name = migrations_names_stack.pop(0)
            migration = self._migrations[migration_name]

            if not migration.dependencies or all(
                dependency in migrations_names for dependency in migration.dependencies
            ):
                migrations_names.append(migration_name)
            else:
                migrations_names_stack.append(migration_name)

        return migrations_names

    async def migrate(self) -> None:
        self._import_migrations()
        self._check_migrations()

        migrations_queue = self._prepare_migrations_queue()
        logger.info(
            f'Migration queue:\r\n{"\r\n".join([f"\t - {migration_name}" for migration_name in migrations_queue])}'
        )

        for migration_name in migrations_queue:
            await self._migrations[migration_name]().run_migration()
