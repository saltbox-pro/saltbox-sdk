from dataclasses import dataclass

from starlette.requests import Request
from starlette.responses import Response


@dataclass(frozen=True)
class MetricInfo:
    request: Request
    response: Response
    duration: float

