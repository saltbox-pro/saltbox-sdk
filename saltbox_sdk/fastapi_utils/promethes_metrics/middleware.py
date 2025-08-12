from http import HTTPStatus
from timeit import default_timer

from prometheus_client import CollectorRegistry
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from saltbox_sdk.exceptions import SaltBoxBaseException
from saltbox_sdk.fastapi_utils.promethes_metrics.aggregator import MetricAggregator
from saltbox_sdk.fastapi_utils.promethes_metrics.metric_info import MetricInfo


class PrometheusExporterMiddleware:

    def __init__(
            self,
            app: ASGIApp,
            registry: CollectorRegistry,
            unavailable_endpoints: set[str] | None = None
        ) -> None:
        self.app = app
        self.unavailable_endpoints = unavailable_endpoints or { "/metrics" }
        self.aggregator = MetricAggregator(registry=registry)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        endpoint = scope.get("path", '')
        if scope["type"] != "http" or endpoint in self.unavailable_endpoints:
           return await self.app(scope, receive, send)

        request_start_time = default_timer()
        response_start_time = None

        status_code= 500
        headers = []

        response_length = 0
        request = Request(scope)

        async def send_wrapper(message: Message) -> None:
            nonlocal headers, status_code, response_start_time, response_length
            if message['type'] == 'http.response.start':
                headers = message['headers']
                status_code = message['status']
                response_start_time = default_timer()
            elif message['type'] == 'http.response.body' and message['body']:
                response_length += len(message['body'])
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except SaltBoxBaseException as ex:
            await self.aggregator.aggregate_exception(request=request, ex=ex)
            raise ex
        finally:
            await self._handle_response(
                request=request,
                status_code=status_code,
                response_length=response_length,
                headers=headers,
                request_start_time=request_start_time,
                response_start_time=response_start_time
            )

    async def _handle_response(
            self,
            request: Request,
            status_code: int,
            response_length: float,
            headers: list,
            request_start_time: float,
            response_start_time: float | None
        ) -> None:
        end_time= default_timer()

        if isinstance(status_code, HTTPStatus):
            status: int = status_code.value
        else:
            status = int(status_code)

        response = Response(
                content=str(response_length),
                headers=Headers(raw=headers),
                status_code=status
                )
        duration = end_time - request_start_time
        duration_to_first_byte = (response_start_time - request_start_time) if response_start_time else None
        info = MetricInfo(
            request=request,
            response=response,
            duration=duration,
            duration_to_first_byte=duration_to_first_byte
        )
        await self.aggregator.aggregate(info=info)

