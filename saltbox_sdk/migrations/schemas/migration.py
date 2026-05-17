from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from saltbox_sdk.db.mongo.schemas_base import IDMixin
from saltbox_sdk.db.schemas_base import CreatedModifiedMixin


class MigrationStatus(StrEnum):
    success = 'success'
    failed = 'failed'


class MigrationReadOnlyFieldsMixin(BaseModel):
    name: str = Field(title='Name')

    status: MigrationStatus = Field(title='Status')
    stages_results: list[Any] = Field(title='Stages results')


class MigrationEditableFieldsMixin(BaseModel): ...


class MigrationCreateSchema(MigrationReadOnlyFieldsMixin, MigrationEditableFieldsMixin): ...


class MigrationUpdateSchema(MigrationEditableFieldsMixin):
    model_config = ConfigDict(extra='ignore')


class MigrationModel(CreatedModifiedMixin, MigrationReadOnlyFieldsMixin, MigrationEditableFieldsMixin, IDMixin): ...
