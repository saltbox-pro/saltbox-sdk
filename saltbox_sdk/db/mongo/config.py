import threading
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import ClassVar

from pymongo import AsyncMongoClient, MongoClient, ReadPreference, WriteConcern
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase as MongoAsyncDatabase
from pymongo.database import Database as MongoSyncDatabase
from pymongo.read_concern import ReadConcern

from saltbox_sdk.config.logger_config import logger
from saltbox_sdk.config.mongo_config import MONGO_SETTINGS


class _MongoClientSingleton:
    instance: ClassVar['_MongoClientSingleton | None'] = None
    lock: ClassVar[threading.Lock] = threading.Lock()
    mongo_client: AsyncMongoClient | None

    def __new__(cls) -> '_MongoClientSingleton':
        with cls.lock:
            if cls.instance is None:
                instance = super().__new__(cls)
                instance.mongo_client = AsyncMongoClient(
                    MONGO_SETTINGS.mongo_url,
                    username=MONGO_SETTINGS.mongo_user or None,
                    password=MONGO_SETTINGS.mongo_password,
                )
                cls.instance = instance
                logger.debug('Mongo client initialized')

        return cls.instance


def _get_mongo_client() -> AsyncMongoClient:
    client = _MongoClientSingleton().mongo_client

    if client is None:
        msg = 'Mongo client is not initialized'
        raise ValueError(msg)

    return client


def get_mongo_db(db_name: str = MONGO_SETTINGS.mongo_db) -> MongoAsyncDatabase:
    return _get_mongo_client()[db_name]


async def reset_mongo_client() -> None:
    instance = _MongoClientSingleton.instance

    if instance is None:
        return

    if instance.mongo_client is not None:
        await instance.mongo_client.close()

    _MongoClientSingleton.instance = None


async def get_mongo() -> MongoAsyncDatabase:
    return get_mongo_db()


def get_sync_mongo_db(db_name: str = MONGO_SETTINGS.mongo_db) -> MongoSyncDatabase:
    client: MongoClient = MongoClient(
        MONGO_SETTINGS.mongo_url,
        username=MONGO_SETTINGS.mongo_user or None,
        password=MONGO_SETTINGS.mongo_password,
    )
    db = client[db_name]
    return db


@asynccontextmanager
async def get_mongo_session_with_transaction(
    session: AsyncClientSession | None = None,
) -> AsyncGenerator[AsyncClientSession, None]:
    if session is not None and session.in_transaction:
        yield session
        return

    mongo_session = session or _get_mongo_client().start_session()

    async with mongo_session as session_with_transaction:
        async with await session_with_transaction.start_transaction(
            read_concern=ReadConcern('snapshot'),
            write_concern=WriteConcern('majority'),
            read_preference=ReadPreference.PRIMARY,
        ):
            yield session_with_transaction
