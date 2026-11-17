from collections.abc import Awaitable, Callable

from pymongo import ReadPreference, WriteConcern
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.errors import InvalidOperation
from pymongo.read_concern import ReadConcern

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.db.mongo.config import _get_mongo_client

type CommitHook = Callable[[], Awaitable[None]]


class MongoTransaction:
    """The current attempt, passed explicitly to nested services."""

    def __init__(self, session: AsyncClientSession) -> None:
        self._session = session
        self._hooks: list[CommitHook] = []
        self._active = True

    @property
    def session(self) -> AsyncClientSession:
        """The session to pass to all MongoDB operations in this attempt."""
        self._check_active()
        return self._session

    def on_commit(self, hook: CommitHook) -> None:
        """Schedule best-effort work after a successful SDK-managed commit."""
        self._check_active()
        self._hooks.append(hook)

    def _check_active(self) -> None:
        if not self._active or not self._session.in_transaction:
            msg = 'Transaction attempt is inactive. Only its owner may commit or abort it.'
            raise InvalidOperation(msg)


async def transact[T](work: Callable[[MongoTransaction], Awaitable[T]]) -> T:
    """Run MongoDB work in a transaction and return the result of the committed attempt.

    Call this at the boundary of a business operation. Pass the supplied
    `MongoTransaction` to nested services. This function owns the session.

    PyMongo can call `work` multiple times. Pass the attempt's session explicitly
    to repositories, use it sequentially, and let MongoDB errors propagate.
    Keep inputs reusable, leave commit and rollback to PyMongo, and keep external
    effects out of `work`.

    Hooks run in registration order after confirmed commit. Failed attempts discard
    their hooks. Hook exceptions are logged and cancellation propagates. Hooks live
    in memory. For reliable delivery, write an outbox record using the same session.
    """

    async def attempt(session: AsyncClientSession) -> tuple[T, list[CommitHook]]:
        tx = MongoTransaction(session)
        try:
            result = await work(tx)
            tx._check_active()
            return result, tx._hooks
        finally:
            tx._active = False

    async with _get_mongo_client().start_session() as session:
        result, hooks = await session.with_transaction(
            attempt,
            read_concern=ReadConcern('snapshot'),
            write_concern=WriteConcern('majority'),
            read_preference=ReadPreference.PRIMARY,
        )

    for hook in hooks:
        try:
            await hook()
        except Exception:
            logger.exception('MongoDB post-commit hook failed')

    return result
