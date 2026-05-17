from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


def sortedset_id_validate(value: str) -> str:
    # TODO @: Validate this
    return value


SortedSetId = Annotated[str | int | float, AfterValidator(sortedset_id_validate)]


class IDMixin(BaseModel):
    id: SortedSetId = Field(title='ID')
