import logging.config
import os
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class LoggerSettings(BaseSettings):
    log_level: str = 'INFO'

    model_config = SettingsConfigDict(env_file=ENV_FILE)


LOGGER_SETTINGS = LoggerSettings()


class LogConfig(BaseModel):
    LOG_FORMAT: str = '%(levelprefix)s [%(filename)s:%(lineno)d] %(message)s'
    LOG_LEVEL: str = LOGGER_SETTINGS.log_level.upper()

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
