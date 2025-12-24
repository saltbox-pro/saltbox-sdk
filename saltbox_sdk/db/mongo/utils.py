from dataclasses import dataclass, field


@dataclass
class AggregatedField:
    field_name: str
    stages: list[dict]
    parent_aggregations: list[str] = field(default_factory=list)


class AggregationsStore:
    def __init__(self, aggregations: list[AggregatedField] | None = None):
        if aggregations is None:
            aggregations = []

        self.__aggregations: dict[str, AggregatedField] = {
            aggregation.field_name: aggregation for aggregation in aggregations
        }

    def __get_pipeline(self, field_name: str, pipeline: list[dict]) -> None:
        aggregation = self.__aggregations[field_name]

        for parent_aggregation in aggregation.parent_aggregations:
            self.__get_pipeline(parent_aggregation, pipeline)

        for stage in aggregation.stages:
            if stage not in pipeline:
                pipeline.append(stage)

    def build_pipeline(self, fields_names: list[str]) -> list[dict]:
        pipeline: list[dict] = []

        for field_key in self.__aggregations.keys():
            if any(field_key == field_name or f'{field_key}.' in field_name for field_name in fields_names):
                self.__get_pipeline(field_key, pipeline)

        return pipeline
