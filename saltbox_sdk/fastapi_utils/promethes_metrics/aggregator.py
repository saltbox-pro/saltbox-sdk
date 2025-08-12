from prometheus_client import CollectorRegistry, Counter, Histogram, Summary
from starlette.requests import Request

from saltbox_sdk.exceptions import SaltBoxBaseException
from saltbox_sdk.fastapi_utils.promethes_metrics.metric_info import MetricInfo


class MetricAggregator:

    def __init__(self, registry: CollectorRegistry) -> None:
        self.registry = registry
        self.request_total = Summary(
            name='http_request_total',
            documentation='Total HTTP requests',
            labelnames=['method', 'route', 'status_code'],
            registry=registry
        )
        self.request_duration = Histogram(
            name='http_request_duration_seconds',
            documentation='Total HTTP request duration in seconds',
            labelnames=['method', 'route', 'status_code'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60],
            registry = registry
        )
        self.ttfb = Histogram(
            name='http_response_ttfb_seconds',
            documentation='Time to first byte in seconds from response',
            labelnames=['method', 'route', 'status_code'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60],
            registry = registry
        )
        self.exceptions_total = Counter(
            name='http_exceptions_total',
            documentation='Raised exceptions',
            labelnames=['route', 'exception_type'],
            registry=registry
        )

    async def aggregate(self, info: MetricInfo) -> None:
        request = info.request
        method = request.scope.get('method', 'GET')

        cl = request.headers.get('content-length')
        try:
            request_length = int(cl) if cl is not None else 0
        except (TypeError, ValueError):
            request_length = 0

        labels = {
                'method': method,
                'route': self._get_route_from_request(request=request),
                'status_code': str(info.response.status_code),
        }
        self.request_total.labels(**labels).observe(request_length)
        self.request_duration.labels(**labels).observe(info.duration)
        if info.duration_to_first_byte is not None:
            self.ttfb.labels(**labels).observe(info.duration_to_first_byte)

    async def aggregate_exception(self, request: Request, ex: SaltBoxBaseException) -> None:
        route = await self._get_route_from_request(request=request)
        self.exceptions_total.labels(route=route, exception_type=ex.__str__).inc()

    async def _get_route_from_request(self, request: Request) -> str:
        root_path: str = request.scope.get("root_path", "")
        route = request.scope.get("route")
        if route and getattr(route, "path_format", None):
            return f"{root_path}{route.path_format}"
        return root_path + request.url.path

