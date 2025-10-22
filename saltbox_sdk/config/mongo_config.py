import os
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class MongoSettings(BaseSettings):
    mongo_db: str = ''
    mongo_host: str = 'mongo'
    mongo_password: str | None = None
    mongo_port: int = 27017
    mongo_user: str = ''
    mongo_replicaset: str = 'rs0'

    @property
    def mongo_url(self) -> str:
        return f'mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/'


MONGO_SETTINGS = MongoSettings()
