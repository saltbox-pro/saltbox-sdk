from typing import Any

from faststream.rabbit import RabbitBroker, RabbitMessage

from saltbox_sdk.event_bus.schemas import EventBusBaseMessage


async def send_message(message: EventBusBaseMessage, queue: str = '', broker: RabbitBroker | None = None) -> None:
    if not broker:
        from saltbox_sdk.event_bus.faststream_app import get_faststream_broker

        broker = get_faststream_broker()

    async with broker as br:
        await br.publish(message=message, queue=queue)


async def send_rpc_message(
    message: EventBusBaseMessage, queue: str = '', response_timeout: float = 3.0, broker: RabbitBroker | None = None
) -> Any:
    if not broker:
        from saltbox_sdk.event_bus.faststream_app import get_faststream_broker

        broker = get_faststream_broker()

    async with broker as br:
        response: RabbitMessage = await br.request(
            message,
            queue=queue,
            timeout=response_timeout,
        )
        return await response.decode()
