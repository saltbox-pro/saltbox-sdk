from typing import Any

from aio_pika.exceptions import AMQPConnectionError
from faststream.rabbit import RabbitBroker, RabbitExchange, RabbitMessage

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.event_bus.schemas import EventBusBaseMessage


async def send_message(
    message: EventBusBaseMessage,
    queue: str = '',
    exchange: RabbitExchange | None = None,
    broker: RabbitBroker | None = None,
) -> None:
    if not broker:
        from saltbox_sdk.event_bus.faststream_app import get_faststream_broker

        broker = get_faststream_broker()

    try:
        async with broker as br:
            _ = await br.publish(message=message, queue=queue, exchange=exchange)
    except AMQPConnectionError as ex:
        logger.warning(f'RabbitMQ is unavailable during startup: {ex}. The broker will reconnect automatically.')


async def send_rpc_message(
    message: EventBusBaseMessage,
    queue: str = '',
    exchange: RabbitExchange | None = None,
    response_timeout: float = 3.0,
    broker: RabbitBroker | None = None,
) -> Any:
    if not broker:
        from saltbox_sdk.event_bus.faststream_app import get_faststream_broker

        broker = get_faststream_broker()

    async with broker as br:
        response: RabbitMessage = await br.request(
            message,
            queue=queue,
            exchange=exchange,
            timeout=response_timeout,
        )
        return await response.decode()
