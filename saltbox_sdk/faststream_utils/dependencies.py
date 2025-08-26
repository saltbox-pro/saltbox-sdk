from typing import Annotated

from faststream import Depends as FSDepends
from redis.asyncio import Redis

from saltbox_sdk.db.mongo import MongoAsyncDatabase
from saltbox_sdk.db.mongo.config import get_mongo
from saltbox_sdk.db.redis.config import get_redis

FSRedisDependency = Annotated[Redis, FSDepends(get_redis)]
FSMongoDependency = Annotated[MongoAsyncDatabase, FSDepends(get_mongo)]
