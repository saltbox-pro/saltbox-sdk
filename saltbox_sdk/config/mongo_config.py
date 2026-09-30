import os
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class MongoSettings(BaseSettings):
    mongo_uri: str | None = None
    mongo_db: str = ''
    mongo_host: str = 'mongo'
    mongo_password: str | None = None
    mongo_port: int = 27017
    mongo_user: str = ''
    mongo_replicaset: str | None = None
    mongo_explain: bool = False

    @property
    def mongo_url(self) -> str:
        if self.mongo_uri:
            return self.mongo_uri

        hosts = ','.join(
            host if ':' in host else f'{host}:{self.mongo_port}'
            for host in (host.strip() for host in self.mongo_host.split(','))
        )
        url = f'mongodb://{hosts}/'

        if self.mongo_replicaset is not None:
            url += f'?replicaSet={self.mongo_replicaset}'

        return url


MONGO_SETTINGS = MongoSettings()
