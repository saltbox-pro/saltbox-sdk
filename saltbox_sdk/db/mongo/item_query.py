from collections.abc import Callable, Iterator, Sequence
from datetime import datetime
from types import UnionType
from typing import Any, Union, get_args, get_origin

from bson import ObjectId
from pydantic import BaseModel

from saltbox_sdk.exceptions import SaltBoxValidationException
from saltbox_sdk.utilities.helpers import recursive_replace_dates

ITEM_OPERATORS = {'$andOnItem': '$and', '$orOnItem': '$or'}
LOGICAL_OPERATORS = {'$and', '$or', '$nor'}


def item_conditions(query: dict) -> Iterator[tuple[str, Any]]:
    for key, value in query.items():
        if key in LOGICAL_OPERATORS:
            if not isinstance(value, list) or not value:
                msg = f'{key} requires a nonempty list of conditions'
                raise SaltBoxValidationException(msg)
            for condition in value:
                if not isinstance(condition, dict) or not condition:
                    msg = f'{key} requires nonempty query objects'
                    raise SaltBoxValidationException(msg)

                yield from item_conditions(condition)
        elif key.startswith('$') or not all(key.split('.')):
            msg = f'Invalid field or logical operator in item group: {key}'
            raise SaltBoxValidationException(msg)
        else:
            yield key, value


def map_item_fields(query: dict, transform: Callable[[str, Any], dict]) -> dict:
    conditions = []
    for key, value in query.items():
        if key in LOGICAL_OPERATORS:
            children = [map_item_fields(child, transform) for child in value]
            if key == '$and':
                conditions.extend(children)
            else:
                conditions.append({key: children})
        else:
            conditions.append(transform(key, value))

    merged: dict = {}

    for condition in conditions:
        if merged.keys() & condition.keys():
            return {'$and': conditions}
        merged.update(condition)

    return merged


def _field_type(annotation: Any, part: str) -> Any:
    if get_origin(annotation) is dict:
        return get_args(annotation)[1]

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        for name, field in annotation.model_fields.items():
            if part in (name, field.alias, field.serialization_alias):
                return field.annotation

    return Any


def _schema_path(model: type[BaseModel], parts: Sequence[str]) -> tuple[str, bool]:
    annotation: Any = model
    boundary = ''

    for index, part in enumerate(parts, start=1):
        annotation = _field_type(annotation, part)

        if get_origin(annotation) in (Union, UnionType):
            types = [arg for arg in get_args(annotation) if arg is not type(None)]
            annotation = types[0] if len(types) == 1 else Any

        if (get_origin(annotation) or annotation) in (list, tuple):
            boundary = '.'.join(parts[:index])
            args = get_args(annotation)
            annotation = args[0] if args else Any

    return boundary, annotation not in (Any, dict) and get_origin(annotation) is not dict


def resolve_item_path(fields: list[str], model: type[BaseModel], configured_paths: Sequence[str]) -> str:
    parts = []

    for segments in zip(*(field.split('.') for field in fields), strict=False):
        if len(set(segments)) != 1:
            break
        parts.append(segments[0])

    common = '.'.join(parts)
    for path in sorted(configured_paths, key=len, reverse=True):
        if common == path or common.startswith(path + '.'):
            return path

    boundary, known = _schema_path(model, parts)
    if boundary:
        return boundary

    if common and not known:
        for field in fields:
            if any(field == path or field.startswith(path + '.') for path in configured_paths):
                break
            if _schema_path(model, field.split('.'))[0]:
                break
        else:
            return common

    msg = f'Item conditions require a shared array: {", ".join(fields)}'

    raise SaltBoxValidationException(msg)


def _combine_membership(left: tuple[bool, set], right: tuple[bool, set], union: bool) -> tuple[bool, set]:
    neg_a, a = left
    neg_b, b = right

    if neg_a == neg_b:
        return neg_a, a | b if union != neg_a else a & b

    excluded, included = (a, b) if neg_a else (b, a)

    return (True, excluded - included) if union else (False, included - excluded)


def _membership(key: str, operand: Any, values: dict[tuple, Any]) -> tuple[bool, set]:
    candidates = operand if key in ('$in', '$nin') else [operand]

    if key not in ('$in', '$nin', '$eq', '$ne') or not isinstance(candidates, list):
        msg = f'Unsupported scalar item predicate: {key}'
        raise SaltBoxValidationException(msg)

    keys = set()

    for value in candidates:
        if not isinstance(value, (str, int, float, datetime, ObjectId, type(None))):
            msg = 'Scalar membership requires scalar values'
            raise SaltBoxValidationException(msg)

        token = (isinstance(value, bool), value)
        values[token] = value
        keys.add(token)

    return key in ('$ne', '$nin'), keys


def scalar_item_match(query: dict) -> dict:
    values: dict[tuple, Any] = {}

    def visit(node: dict) -> tuple[bool, set]:
        result: tuple[bool, set] = (True, set())

        for key, value in node.items():
            if key in LOGICAL_OPERATORS:
                union = key != '$and'
                current: tuple[bool, set] = (not union, set())
                for child in value:
                    current = _combine_membership(current, visit(child), union)
                if key == '$nor':
                    current = not current[0], current[1]
            else:
                predicates = value if isinstance(value, dict) else {'$eq': value}
                current = (True, set())
                for operator, operand in predicates.items():
                    current = _combine_membership(current, _membership(operator, operand, values), False)
            result = _combine_membership(result, current, False)

        return result

    negative, selected = visit(recursive_replace_dates(query))

    return {'$nin' if negative else '$in': [value for token, value in values.items() if token in selected]}
