from faststream import FastStream
from faststream.broker.types import BrokerMiddleware
from faststream.rabbit import RabbitBroker
from faststream.types import Lifespan

from saltbox_sdk.config.rabbitmq_config import RABBIT_SETTINGS


def get_faststream_broker(middlewares: list[BrokerMiddleware] | None = None) -> RabbitBroker:
    if middlewares:
        return RabbitBroker(url=RABBIT_SETTINGS.url, middlewares=middlewares)

    return RabbitBroker(url=RABBIT_SETTINGS.url)


def get_faststream_app(
    routers: list | None = None,
    lifespan: Lifespan | None = None,
    middlewares: list[BrokerMiddleware] | None = None,
) -> FastStream:
    if routers is None:
        routers = []

    broker = get_faststream_broker(middlewares)

    for router in routers:
        broker.include_router(router)

    return FastStream(broker, lifespan=lifespan)
