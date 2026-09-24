import csv
import io
import json
import re
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from fastapi.responses import StreamingResponse

from saltbox_sdk.utilities.helpers import utc_now

FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')
UTF8_BOM = '\ufeff'


def to_csv_value(value: Any) -> Any:
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict | list):
        value = json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"

    return value


async def iter_csv(
    columns: list[tuple[str, str]], rows: AsyncIterator[dict[str, Any]], chunk_rows: int = 1000
) -> AsyncIterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    buffer.write(UTF8_BOM)
    writer.writerow([header for header, _ in columns])
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate()
    buffered_rows = 0

    async for row in rows:
        writer.writerow([to_csv_value(row.get(key)) for _, key in columns])
        buffered_rows += 1

        if buffered_rows >= chunk_rows:
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate()
            buffered_rows = 0

    yield buffer.getvalue()


def csv_response(
    columns: list[tuple[str, str]], rows: AsyncIterator[dict[str, Any]], filename_parts: list[str]
) -> StreamingResponse:
    name = re.sub(r'[^\w.-]', '_', '_'.join(filename_parts), flags=re.ASCII)
    filename = f'{name}_{utc_now():%Y%m%d_%H%M%S}.csv'

    return StreamingResponse(
        iter_csv(columns, rows),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
