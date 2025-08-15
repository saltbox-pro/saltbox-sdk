import re
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, PlainSerializer

# 2025-11-14
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# 2025-11-14T09:50:38.000+00:00
DATETIME_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}\+\d{2}:\d{2}$')
# 2025-11-14T09:50:38
DATETIME_PATTERN_NO_MS = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')
# 2025-03-12 00:00:00
DATETIME_PATTERN_NO_TZ = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
# 2025-04-11T09:00:49.331Z
DATETIME_PATTERN_Z = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_now_stamp_str() -> str:
    return str(datetime.now(UTC).timestamp())


def datetime_now_sec() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def make_aware(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def format_iso8601_z(dt: datetime) -> str:
    """
    Format datetime to ISO 8601 with Z-suffix (UTC).
    Example: 2025-04-08T11:39:06.140000Z
    """
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


Iso8601ZDatetime = Annotated[
    datetime,
    AfterValidator(make_aware),
    PlainSerializer(format_iso8601_z, when_used='json'),
    'Aware datetime serializing with Z-suffix. Unaware datetime decides UTC.',
]


def recursive_replace_dates(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: recursive_replace_dates(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [recursive_replace_dates(item) for item in obj]
    elif isinstance(obj, str) and DATE_PATTERN.match(obj):
        return datetime.strptime(obj, '%Y-%m-%d').replace(tzinfo=UTC)
    elif isinstance(obj, str) and DATETIME_PATTERN.match(obj):
        return datetime.strptime(obj, '%Y-%m-%dT%H:%M:%S.%f%z')
    elif isinstance(obj, str) and DATETIME_PATTERN_NO_MS.match(obj):
        return datetime.strptime(obj, '%Y-%m-%dT%H:%M:%S').replace(tzinfo=UTC)
    elif isinstance(obj, str) and DATETIME_PATTERN_NO_TZ.match(obj):
        return datetime.strptime(obj, '%Y-%m-%d %H:%M:%S').replace(tzinfo=UTC)
    elif isinstance(obj, str) and DATETIME_PATTERN_Z.match(obj):
        return datetime.strptime(obj, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=UTC)
    else:
        return obj


def match_query(obj: dict, query: dict) -> bool:  # noqa: C901
    """Func for matching mongo-like query conditions against an object.
    Example query:
    {
        '$and': [
            {'field1': 'value1'},
            {'field2': {'$gt': 10}},
            {'field3': {'$in': ['value2', 'value3']}}
        ]
    }
    e.g. for filtering Jobs from Redis in list endpoint
    """

    def match_condition(field: str, cond: Any) -> bool:
        if isinstance(cond, dict):
            for op, val in cond.items():
                if op == '$in':
                    if obj.get(field) not in val:
                        return False
                elif op == '$gt':
                    if obj.get(field) <= val:
                        return False
                elif op == '$lt':
                    if obj.get(field) >= val:
                        return False
                else:
                    return False
            return True
        else:
            return obj.get(field) == cond or obj.get(field) == str(cond)

    if '$and' in query:
        return all(match_query(obj, subq) for subq in query['$and'])
    if '$or' in query:
        return any(match_query(obj, subq) for subq in query['$or'])

    for field, cond in query.items():
        if not match_condition(field, cond):
            return False
    return True
