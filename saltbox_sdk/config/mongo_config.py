import os
from pathlib import Path

from pydantic_settings import BaseSettings

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class MongoSettings(BaseSettings):
    mongo_db: str = ''
    mongo_password: str | None = None
    mongo_port: int = 27017
    mongo_user: str = ''

    @property
    def mongo_url(self) -> str:
        return f'mongodb://{self.mongo_user}:{self.mongo_password}@mongo:{self.mongo_port}/'


MONGO_SETTINGS = MongoSettings()
