from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, CollectorRegistry, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from saltbox_sdk.fastapi_utils.promethes_metrics.middleware import PrometheusExporterMiddleware


class PrometheusExporter:
    _ENDPOINT = '/metrics'

    def __init__(self, app: FastAPI, include_in_shema: bool = True, registry: CollectorRegistry | None = None) -> None:
        self.app = app
        self.include_in_schema = include_in_shema
        self.registry = registry or REGISTRY

    def expose_metrics(self) -> None:
        self.app.add_middleware(
            middleware_class=PrometheusExporterMiddleware,
            registry=self.registry,
            unavailable_endpoints={self._ENDPOINT},
        )

        def metrics(_: Request) -> Response:
            response = Response(content=generate_latest(registry=self.registry))
            response.headers['Content-Type'] = CONTENT_TYPE_LATEST
            return response

        self.app.add_route(path=self._ENDPOINT, route=metrics, include_in_schema=self.include_in_schema)
