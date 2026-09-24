import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


class AbstractAggregationStage(ABC):
    @abstractmethod
    def render_stage(self) -> dict[str, Any]: ...


class CustomAggregationStage(AbstractAggregationStage):
    def __init__(self, stage: dict[str, Any]):
        self.stage = stage

    def render_stage(self) -> dict[str, Any]:
        return self.stage


class AddFieldsAggregationStage(AbstractAggregationStage):
    def __init__(self, *, fields: dict[str, str | dict]) -> None:
        self.fields = fields

    def render_stage(self) -> dict[str, Any]:
        return {'$addFields': self.fields}


class ProjectAggregationStage(AbstractAggregationStage):
    def __init__(self, *, fields: dict[str, Literal[0, 1] | bool | str | dict]) -> None:
        self.fields = fields

    def render_stage(self) -> dict[str, Any]:
        return {'$project': self.fields}


class UnsetAggregationStage(AbstractAggregationStage):
    def __init__(self, *, fields: list[str]) -> None:
        self.fields = fields

    def render_stage(self) -> dict[str, Any]:
        return {'$unset': self.fields}


class GroupAggregationStage(AbstractAggregationStage):
    def __init__(self, *, group_id: int | str | dict[str, Any] | None, fields: dict[str, Any]) -> None:
        self.group_id = group_id
        self.fields = fields

    def render_stage(self) -> dict[str, Any]:
        return {'$group': {'_id': self.group_id, **self.fields}}


class MatchAggregationStage(AbstractAggregationStage):
    def __init__(self, *, query: dict[str, Any]) -> None:
        self.query = query

    def render_stage(self) -> dict[str, Any]:
        return {'$match': self.query}


class LookupAggregationStage(AbstractAggregationStage):
    def __init__(
        self,
        *,
        from_collection: str,
        local_field: str | None = None,
        foreign_field: str | None = None,
        let: dict[str, Any] | None = None,
        pipeline: list[dict[str, Any] | AbstractAggregationStage] | None = None,
        as_field: str,
    ) -> None:
        self.from_collection = from_collection
        self.local_field = local_field
        self.foreign_field = foreign_field
        self.let = let
        self.pipeline = pipeline
        self.as_field = as_field

        if (self.local_field is None or self.foreign_field is None) and self.pipeline is None:
            msg = 'Must specify "local_field" and "foreign_field" or "pipeline"'
            raise ValueError(msg)

    def render_stage(self) -> dict[str, Any]:
        result: dict[str, Any] = {'from': self.from_collection, 'as': self.as_field}

        if self.local_field is not None:
            result['localField'] = self.local_field
        if self.foreign_field is not None:
            result['foreignField'] = self.foreign_field
        if self.let is not None:
            result['let'] = self.let
        if self.pipeline is not None:
            result['pipeline'] = [
                pipline_stage.render_stage() if isinstance(pipline_stage, AbstractAggregationStage) else pipline_stage
                for pipline_stage in self.pipeline
            ]

        return {'$lookup': result}


class UnwindAggregationStage(AbstractAggregationStage):
    def __init__(
        self,
        *,
        path: str,
        include_array_index: str | None = None,
        preserve_null_and_empty_arrays: bool = False,
    ) -> None:
        self.path = path
        self.include_array_index = include_array_index
        self.preserve_null_and_empty_arrays = preserve_null_and_empty_arrays

        if self.include_array_index and self.include_array_index.startswith('$'):
            msg = '"include_array_index" must start with "$"'
            raise ValueError(msg)

    def render_stage(self) -> dict[str, Any]:
        result = {'path': self.path, 'preserveNullAndEmptyArrays': self.preserve_null_and_empty_arrays}

        if self.include_array_index is not None:
            result['includeArrayIndex'] = self.include_array_index

        return {'$unwind': result}


class AnySearchAggregationStage(AbstractAggregationStage):
    def __init__(self, *, search: str, escape: bool = True) -> None:
        self.search = search
        self.escape = escape

    def render_stage(self) -> dict[str, Any]:
        value_as_string = {'$convert': {'input': '$$kv.v', 'to': 'string', 'onError': '', 'onNull': ''}}
        regex = re.escape(self.search) if self.escape else self.search
        search_match = {'$regexMatch': {'input': value_as_string, 'regex': regex, 'options': 'i'}}

        return {
            '$match': {
                '$expr': {
                    '$anyElementTrue': {'$map': {'input': {'$objectToArray': '$$ROOT'}, 'as': 'kv', 'in': search_match}}
                }
            }
        }


@dataclass
class AggregatedField:
    field_name: str
    stages: list[AbstractAggregationStage]
    parent_aggregations: list[str] = field(default_factory=list)


class AggregationsStore:
    def __init__(self, aggregations: list[AggregatedField] | None = None):
        if aggregations is None:
            aggregations = []

        self.__aggregations: dict[str, AggregatedField] = {
            aggregation.field_name: aggregation for aggregation in aggregations
        }

    def __get_pipeline(self, field_name: str, pipeline: list[dict], stages_to_exclude: list[dict]) -> None:
        aggregation = self.__aggregations[field_name]

        for parent_aggregation in aggregation.parent_aggregations:
            self.__get_pipeline(field_name=parent_aggregation, pipeline=pipeline, stages_to_exclude=stages_to_exclude)

        for stage in aggregation.stages:
            rendered_stage = stage.render_stage()
            if rendered_stage not in pipeline and rendered_stage not in stages_to_exclude:
                pipeline.append(rendered_stage)

    def build_pipeline(self, fields_names: list[str], stages_to_exclude: list[dict] | None = None) -> list[dict]:
        if stages_to_exclude is None:
            stages_to_exclude = []

        pipeline: list[dict] = []

        for field_key in self.__aggregations.keys():
            if any(field_key == field_name or f'{field_key}.' in field_name for field_name in fields_names):
                self.__get_pipeline(field_name=field_key, pipeline=pipeline, stages_to_exclude=stages_to_exclude)

        return pipeline
