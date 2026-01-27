import re
from abc import ABC, abstractmethod
from datetime import datetime
from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import AfterValidator, BaseModel
from pymongo.asynchronous.database import AsyncDatabase
from redis.asyncio import Redis

_MIGRATION_ID_PATTERN = r'^\d{4}__[a-z0-9_]+$'

def validate_migration_id(id: str) -> str:
    if id and not re.search(_MIGRATION_ID_PATTERN, id):
        msg = f'Invalid migration id: {id}. Must match XXXX__comment (e.g., 0001__create_users)'
        raise ValueError(msg)
    return id

MigrationId = Annotated[str, AfterValidator(validate_migration_id)]


class MigrationExecuteStatus(StrEnum):
    SUCCESS = 'success'
    FAIL = 'fail'


class MigrationState(BaseModel):
    id: MigrationId
    status: MigrationExecuteStatus
    applied_at: datetime


class BaseMigration[T: AsyncDatabase | Redis](ABC):
    id: ClassVar[MigrationId]
    comment: ClassVar[str | None] = None
    created_at: ClassVar[datetime]
    dependencies: ClassVar[list[MigrationId]] = []

    @abstractmethod
    async def action(self, db: T) -> None:
        ...
