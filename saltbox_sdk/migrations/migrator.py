from collections.abc import Iterator
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

    @staticmethod
    def _iter_subclasses(cls: type[BaseMigration]) -> Iterator[type[BaseMigration]]:
        for subclass in cls.__subclasses__():
            yield subclass
            yield from Migrator._iter_subclasses(subclass)

    def _import_migrations(self) -> None:
        self._migrations = {}
        packages_names: list[str] = []

        for module_path in self._modules_paths:
            module_name = '.'.join(module_path)
            package_name = f'{module_name}.migrations'

            try:
                package = import_module(package_name)
            except ModuleNotFoundError as e:
                if e.name != package_name:
                    raise

                logger.info(f'Module {module_name} has no migrations')
                continue

            packages_names.append(package_name)

            for _, name, _ in iter_modules(package.__path__):
                import_module(f'{package_name}.{name}')

        packages_prefixes = tuple(f'{package_name}.' for package_name in packages_names)

        for migration in self._iter_subclasses(BaseMigration):
            if not migration.__module__.startswith(packages_prefixes):
                continue

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
