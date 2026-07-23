import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class RabbitSettings(BaseSettings):
    host: str = 'rabbitmq'
    port: int = 5672
    admin: str
    amqp_password: str
    fail_fast: bool = False  # Keep trying to connect

    @property
    def url(self) -> str:
        return f'amqp://{self.admin}:{self.amqp_password}@{self.host}:{self.port}/'

    model_config = SettingsConfigDict(
        env_file=ENV_FILE, env_prefix='RABBITMQ_', extra='ignore', secrets_dir='/run/secrets'
    )


RABBIT_SETTINGS = RabbitSettings()  # ty: ignore[missing-argument]
