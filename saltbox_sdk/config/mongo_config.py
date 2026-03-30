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
    mongo_replicaset: str | None = None
    mongo_explain: bool = False

    @property
    def mongo_url(self) -> str:
        url = f'mongodb://{self.mongo_user}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/'

        if self.mongo_replicaset is not None:
            url += f'?replicaSet={self.mongo_replicaset}'

        return url


MONGO_SETTINGS = MongoSettings()
