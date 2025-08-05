import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class RabbitSettings(BaseSettings):
    host: str = 'rabbitmq'
    port: int = 5672
    user: str = 'guest'
    password: str = 'guest'  # noqa: S105

    @property
    def url(self) -> str:
        return f'amqp://{self.user}:{self.password}@{self.host}:{self.port}/'

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix='RABBITMQ_', extra='ignore')


RABBIT_SETTINGS = RabbitSettings()
