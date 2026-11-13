from collections.abc import Awaitable, Callable
from typing import Protocol


class IncomingTaskDelivery(Protocol):
    async def ack(self) -> None: ...

    async def reject(self, requeue: bool = False) -> None: ...


async def defer_task_delivery(
    delivery: IncomingTaskDelivery,
    publish: Callable[[], Awaitable[None]],
) -> None:
    """Acknowledge the original only after confirmed publication of its successor."""
    try:
        await publish()
    except BaseException:
        await delivery.reject(requeue=True)
        raise
    await delivery.ack()
