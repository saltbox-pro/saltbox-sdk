from datetime import timedelta

from faststream import FastStream
from faststream.broker.types import BrokerMiddleware
from faststream.rabbit import RabbitBroker
from faststream.types import Lifespan

from saltbox_sdk.config.rabbitmq_config import RABBIT_SETTINGS

RABBITMQ_RECONNECT_INTERVAL: timedelta = timedelta(seconds=5)

def get_faststream_broker(middlewares: list[BrokerMiddleware] | None = None) -> RabbitBroker:
    if middlewares:
        return RabbitBroker(url=RABBIT_SETTINGS.url, middlewares=middlewares)

    return RabbitBroker(
        url=RABBIT_SETTINGS.url,
        fail_fast=False,
        reconnect_interval=RABBITMQ_RECONNECT_INTERVAL.total_seconds()
    )


def get_faststream_app(
    routers: list | None = None,
    lifespan: Lifespan | None = None,
    broker: RabbitBroker | None = None,
    middlewares: list[BrokerMiddleware] | None = None,
) -> FastStream:
    if routers is None:
        routers = []

    if broker is None:
        broker = get_faststream_broker(middlewares)
    else:
        for middleware in middlewares or []:
            if middleware not in broker._middlewares:
                broker.add_middleware(middleware)

    for router in routers:
        broker.include_router(router)

    return FastStream(broker, lifespan=lifespan)
