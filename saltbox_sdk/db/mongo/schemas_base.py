from enum import IntEnum
from typing import Annotated, Any, Literal, NotRequired, TypedDict

import pydantic
from bson.errors import InvalidId
from bson.objectid import ObjectId
from pydantic import AfterValidator, BaseModel, Field, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core.core_schema import (
    CoreSchema,
    no_info_plain_validator_function,
    plain_serializer_function_ser_schema,
    str_schema,
)

from saltbox_sdk.db.schemas_base import SourceOnlySchema

IS_PYDANTIC_V2_10 = int(pydantic.VERSION.split('.')[0]) >= 2 and int(pydantic.VERSION.split('.')[1]) >= 10
ALLOWED_MONGO_PIPELINE_QUERY_KEYS = [
    '$and',
    '$or',
    '$nor',
    '$not',
    '$eq',
    '$ne',
    '$gt',
    '$gte',
    '$lt',
    '$lte',
    '$in',
    '$nin',
    '$exists',
    '$type',
    '$expr',
    '$jsonSchema',
    '$mod',
    '$regex',
    '$geoIntersects',
    '$geoWithin',
    '$near',
    '$nearSphere',
    '$all',
    '$elemMatch',
    '$size',
    '$bitsAllClear',
    '$bitsAllSet',
    '$bitsAnyClear',
    '$bitsAnySet',
]
ALLOWED_MONGO_QUERY_KEYS = [
    *ALLOWED_MONGO_PIPELINE_QUERY_KEYS,
    '$text',
    '$where',
    '$geoNear',
    '$comment',
    '$meta',
    '$slice',
]


def validate_mongo_query(value: dict[str, Any]) -> dict[str, Any]:
    for key, val in value.items():
        if key.startswith('$') and key not in ALLOWED_MONGO_QUERY_KEYS:
            msg = f'Invalid or unsupported operator `{key}`'
            raise ValueError(msg)
        if isinstance(val, dict):
            validate_mongo_query(val)

        if key in {'$and', '$or', '$in'} and not isinstance(val, list):
            msg = f'Value for `{key}` must be a `list`'
            raise ValueError(msg)
    return value


def validate_pipeline_query(value: dict[str, Any]) -> dict[str, Any]:
    for key, val in value.items():
        if key.startswith('$') and key not in ALLOWED_MONGO_PIPELINE_QUERY_KEYS:
            msg = f'Invalid or unsupported operator `{key}`'
            raise ValueError(msg)
        if isinstance(val, dict):
            validate_pipeline_query(val)

        if key in {'$and', '$or', '$in'} and not isinstance(val, list):
            msg = f'Value for `{key}` must be a `list`'
            raise ValueError(msg)
    return value


MongoQuery = Annotated[dict[str, Any], AfterValidator(validate_mongo_query)]

PipelineMongoQuery = Annotated[dict[str, Any], AfterValidator(validate_pipeline_query)]

MongoQueryField: dict[str, Any] = Field(
    default_factory=dict,
    title='MongoDB Query',
    description='A valid MongoDB query dictionary',
    examples=[
        {'some_field': 'Some value'},
        {'some.with.path.field': 'Some other value'},
    ],
    json_schema_extra={'example': {'data_obj.data_field': {'$not': {'$regex': 'some value'}}}},
)


class QueryParams(BaseModel):
    query: MongoQuery = MongoQueryField


class SortOrder(IntEnum):
    ASC = 1
    DESC = -1


class SortParams(BaseModel):
    sort: dict[str, SortOrder] | None = None


class PyObjectId(ObjectId):
    """
    Object Id field. Compatible with Pydantic.
    """

    @classmethod
    def _validate(cls, v: Any) -> 'PyObjectId':
        if isinstance(v, bytes):
            v = v.decode('utf-8')
        if not v:
            msg = 'Invalid ObjectId value'
            raise ValueError(msg)
        try:
            return PyObjectId(v)
        except (InvalidId, TypeError):
            msg = 'Id must be of type PydanticObjectId'
            raise ValueError(msg) from None

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: type[Any], handler: GetCoreSchemaHandler) -> CoreSchema:
        if not IS_PYDANTIC_V2_10:
            return no_info_plain_validator_function(
                cls._validate,
                metadata={
                    'pydantic_js_input_core_schema': str_schema(
                        pattern='^[0-9a-f]{24}$',
                        min_length=24,
                        max_length=24,
                    )
                },
                serialization=plain_serializer_function_ser_schema(
                    lambda instance: str(instance),
                    return_schema=str_schema(),
                    when_used='json',
                ),
            )
        return no_info_plain_validator_function(
            cls._validate,
            json_schema_input_schema=str_schema(
                pattern='^[0-9a-f]{24}$',
                min_length=24,
                max_length=24,
            ),
            serialization=plain_serializer_function_ser_schema(
                lambda instance: str(instance),
                return_schema=str_schema(),
                when_used='json',
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: CoreSchema, handler: GetJsonSchemaHandler) -> JsonSchemaValue:
        json_schema = handler(schema)
        json_schema.update(
            type='string',
            example='5eb7cf5a86d9755df3a6c593',
        )
        return json_schema


class IDMixin:
    id: PyObjectId = Field(title='ID', alias='_id', serialization_alias='id')


class SourceWithIdOnlySchema(SourceOnlySchema, IDMixin): ...


class EmptyModel(pydantic.BaseModel, IDMixin): ...


class TreeMixin:
    parent_id: PyObjectId | None = Field(title='Parent ID', default=None)


class BaseTreeModel(pydantic.BaseModel, IDMixin, TreeMixin): ...


class TimeSeriesConfig(TypedDict):
    timeField: str
    metaField: NotRequired[str]
    granularity: NotRequired[Literal['seconds', 'minutes', 'hours']]
    bucketMaxSpanSeconds: NotRequired[int]
    bucketRoundingSeconds: NotRequired[int]  # опционально, если нужен точный контроль окон
