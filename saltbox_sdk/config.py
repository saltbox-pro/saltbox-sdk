import logging.config
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class Settings(BaseSettings):
    log_level: str = 'INFO'
    base_url: str
    discovery_url: str
    service_name: str
    service_title: str
    service_description: str
    service_vendor: str
    service_type: str
    instance_host: str
    instance_port: int
    front_container_name: str
    front_container_port: int

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix='DISCOVERY_', extra='ignore')


SETTINGS = Settings()


class MongoSettings(BaseSettings):
    mongo_db: str = ''
    mongo_password: str | None = None
    mongo_port: int = 27017
    mongo_user: str = ''

    @property
    def mongo_url(self) -> str:
        return f'mongodb://{self.mongo_user}:{self.mongo_password}@mongo:{self.mongo_port}/'


MONGO_SETTINGS = MongoSettings()


class RedisSettings(BaseSettings):
    redis_ca_cert: str | None = Field(None, description='Path to file of concatenated PEM certs')
    redis_password: str | None = None
    redis_tls_verification: Literal['none', 'optional', 'required'] = 'required'
    redis_url: str = ''
    redis_username: str | None = None

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


class LogConfig(BaseModel):
    LOG_FORMAT: str = '%(levelprefix)s [%(filename)s:%(lineno)d] %(message)s'
    LOG_LEVEL: str = SETTINGS.log_level.upper()

    version: int = 1
    disable_existing_loggers: bool = False
    formatters: dict = {
        'default': {
            '()': 'uvicorn.logging.DefaultFormatter',
            'datefmt': '%Y-%m-%d %H:%M:%S',
            'fmt': LOG_FORMAT,
        },
    }
    handlers: dict = {
        'default': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'stream': 'ext://sys.stderr',
        },
    }
    loggers: dict = {
        'saltbox_sdk': {
            'handlers': ['default'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    }


LOG_CONFIG = LogConfig()

logging.config.dictConfig(LOG_CONFIG.model_dump())

logger = logging.getLogger('saltbox_sdk')
