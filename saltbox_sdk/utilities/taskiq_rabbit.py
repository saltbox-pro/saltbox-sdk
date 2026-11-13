import hashlib
import math
from collections.abc import AsyncGenerator, Awaitable, Callable
from datetime import timedelta
from functools import cached_property
from typing import Annotated, Any
from uuid import uuid4

from aio_pika import DeliveryMode, Message
from aio_pika.abc import AbstractIncomingMessage, AbstractQueue
from pamqp.commands import Basic
from taskiq import AckableMessage, BrokerMessage, Context, TaskiqDepends, TaskiqMessage
from taskiq.exceptions import NoResultError
from taskiq_aio_pika import AioPikaBroker
from taskiq_aio_pika.exceptions import NoStartupError
from taskiq_aio_pika.utils import merge_async_iterables

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.utilities.taskiq import UniqueIdMiddleware
from saltbox_sdk.utilities.taskiq_delivery import defer_task_delivery
from saltbox_sdk.utilities.taskiq_lock import UniqueTaskLock


class SaltboxAioPikaBroker(AioPikaBroker):
    DELIVERY_LABEL = '_saltbox_delivery'

    @cached_property
    def _deliveries(self) -> dict[str, AbstractIncomingMessage]:
        return {}

    @cached_property
    def _blocked_acks(self) -> set[str]:
        return set()

    async def _listen_queue(
        self, queue: AbstractQueue, consumer_args: dict[str, Any]
    ) -> AsyncGenerator[AckableMessage, None]:
        async with queue.iterator(**consumer_args) as iterator:
            async for incoming in iterator:
                message = self.formatter.loads(incoming.body)
                delivery_id = uuid4().hex
                message.labels[self.DELIVERY_LABEL] = delivery_id
                if message.labels.get(UniqueIdMiddleware.LOCK_KEY_LABEL):
                    message.labels['ack_type'] = 'when_saved'
                self._deliveries[delivery_id] = incoming
                yield AckableMessage(
                    data=self.formatter.dumps(message).message,
                    ack=self._ack_callback(delivery_id, incoming),
                )

    def _ack_callback(self, delivery_id: str, incoming: AbstractIncomingMessage) -> Callable[[], Awaitable[None]]:
        async def ack() -> None:
            if delivery_id in self._blocked_acks and not incoming.processed:
                return
            if not incoming.processed:
                await incoming.ack()
            self._deliveries.pop(delivery_id, None)
            self._blocked_acks.discard(delivery_id)

        return ack

    async def listen(self) -> AsyncGenerator[AckableMessage, None]:
        if self.read_channel is None:
            msg = 'Call startup before listening'
            raise NoStartupError(msg)
        await self.read_channel.set_qos(prefetch_count=self._qos)
        queues = await self._declare_queues(self.read_channel)
        async for message in merge_async_iterables(
            *[
                self._listen_queue(queue, arguments)
                for queue, arguments in queues
                if self._delay_queue is None or queue.name != self._delay_queue.name
            ]
        ):
            yield message

    async def acquire_unique_task(self, message: TaskiqMessage) -> UniqueTaskLock:
        middleware = next(item for item in self.middlewares if isinstance(item, UniqueIdMiddleware))
        incoming = self._deliveries[message.labels[self.DELIVERY_LABEL]]
        try:
            acquired = await middleware.acquire_execution(message)
        except Exception:
            message.labels[middleware.DEFERRED_LABEL] = True
            self._blocked_acks.add(message.labels[self.DELIVERY_LABEL])
            await incoming.reject(requeue=True)
            logger.exception('Failed to acquire unique task execution lock')
            raise NoResultError from None
        if acquired:
            lock = middleware.get_lock(message)
            if lock is None:
                msg = 'Unique task dependency requires a reserved task'
                raise RuntimeError(msg)
            return lock

        successor = message.model_copy(deep=True)
        successor.labels.pop(self.DELIVERY_LABEL, None)
        successor.labels['delay'] = '1'
        message.labels[middleware.DEFERRED_LABEL] = True
        self._blocked_acks.add(message.labels[self.DELIVERY_LABEL])

        async def publish() -> None:
            await self.kick(self.formatter.dumps(successor))

        try:
            await defer_task_delivery(incoming, publish)
        except Exception:
            logger.exception('Failed to defer a busy unique task')
        raise NoResultError

    async def kick(self, message: BrokerMessage) -> None:
        delay_label = message.labels.get('delay')
        if delay_label is None:
            await super().kick(message)
            return
        delay = float(delay_label)
        if not math.isfinite(delay) or delay < 0:
            msg = 'Task delay must be finite and non-negative'
            raise ValueError(msg)
        if self.write_channel is None:
            msg = 'Call startup before publishing delayed tasks'
            raise NoStartupError(msg)
        if not self.write_channel.publisher_confirms:
            msg = 'Delayed tasks require publisher confirms'
            raise RuntimeError(msg)

        routing_key = str(message.labels.get(self._label_for_routing, ''))
        if not routing_key and len(self._task_queues) == 1:
            queue = self._task_queues[0]
            routing_key = queue.routing_key or queue.name
        if not routing_key:
            msg = 'A delayed task must specify its destination queue'
            raise ValueError(msg)

        digest = hashlib.sha256(f'{self._exchange.name}\0{routing_key}'.encode()).hexdigest()
        delay_queue = await self.write_channel.declare_queue(
            name=f'taskiq.delay.v2.{digest}',
            durable=True,
            arguments={
                'x-queue-type': 'quorum',
                'x-dead-letter-exchange': self._exchange.name,
                'x-dead-letter-routing-key': routing_key,
                'x-dead-letter-strategy': 'at-least-once',
                'x-overflow': 'reject-publish',
            },
        )
        priority_label = message.labels.get(self._label_for_priority)
        outgoing = Message(
            body=message.message,
            headers={'task_id': message.task_id, 'task_name': message.task_name, **message.labels},
            delivery_mode=DeliveryMode.PERSISTENT,
            priority=int(priority_label) if priority_label is not None else None,
            expiration=timedelta(seconds=delay),
        )
        confirmation = await self.write_channel.default_exchange.publish(
            outgoing, routing_key=delay_queue.name, mandatory=True
        )
        if not isinstance(confirmation, Basic.Ack):
            msg = 'Delayed task publication was not acknowledged by RabbitMQ'
            raise RuntimeError(msg)


async def get_unique_task_lock(context: Annotated[Context, TaskiqDepends()]) -> UniqueTaskLock:
    if not isinstance(context.broker, SaltboxAioPikaBroker):
        msg = 'Unique task execution requires SaltboxAioPikaBroker'
        raise RuntimeError(msg)
    return await context.broker.acquire_unique_task(context.message)
