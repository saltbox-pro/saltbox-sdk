from prometheus_client import CollectorRegistry, Counter, Histogram, Summary
from starlette.requests import Request

from saltbox_sdk.fastapi_utils.promethes_metrics.metric_info import MetricInfo


class MetricAggregator:
    def __init__(self, registry: CollectorRegistry) -> None:
        self.registry = registry
        self.request_total = Counter(
            name='http_request_total', documentation='Total number of HTTP requests', registry=registry
        )
        self.request_endpoint = Summary(
            name='http_request_endpoint',
            documentation='Total number of HTTP requests grouped by endpoint URL',
            labelnames=['endpoint', 'status_code'],
            registry=registry,
        )
        self.request_duration = Histogram(
            name='http_request_duration_seconds',
            documentation='Total number of HTTP requests duration in seconds',
            labelnames=['endpoint', 'status_code'],
            buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60],
            registry=registry,
        )
        self.error_total = Counter(
            name='http_error_total',
            documentation='Total number of HTTP error responses',
            labelnames=['endpoint', 'status_code'],
            registry=registry,
        )

    async def aggregate(self, info: MetricInfo) -> None:
        request = info.request
        cl = request.headers.get('content-length')
        try:
            request_length = int(cl) if cl is not None else 0
        except (TypeError, ValueError):
            request_length = 0

        status = info.response.status_code
        route = self._get_route_from_request(request=request)
        labels = {
            'endpoint': f'{request.method} {route}',
            'status_code': str(status),
        }
        if status >= 400:
            self.error_total.labels(**labels).inc()
        self.request_total.inc()
        self.request_endpoint.labels(**labels).observe(request_length)
        self.request_duration.labels(**labels).observe(info.duration)

    @staticmethod
    def _get_route_from_request(request: Request) -> str:
        root_path: str = request.scope.get("root_path", "")
        return root_path + request.url.path
