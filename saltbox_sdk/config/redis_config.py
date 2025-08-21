import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class RedisSettings(BaseSettings):
    redis_ca_cert: str | None = Field(None, description='Path to file of concatenated PEM certs')
    redis_password: str | None = None
    redis_tls_verification: Literal['none', 'optional', 'required'] = 'required'
    redis_url: str = 'redis://localhost:6379/0'
    redis_username: str | None = None

    model_config = SettingsConfigDict(env_file=ENV_FILE, extra='ignore')

    @property
    def redis_connection_kwargs(self) -> dict[str, Any]:
        """
        Additional options for redis.*.from_url() group of methods
        """
        result = {
            'username': self.redis_username,
            'password': self.redis_password,
        }
        if self.redis_url.startswith('rediss:'):
            result |= {
                'ssl_cert_reqs': self.redis_tls_verification,
                'ssl_ca_certs': self.redis_ca_cert,
            }
        return result


REDIS_SETTINGS = RedisSettings()
