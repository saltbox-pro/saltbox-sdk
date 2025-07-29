import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class DiscoverySettings(BaseSettings):
    server_outer_socket: str
    server_scheme: str
    server_ws_scheme: str
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


DISCOVERY_SETTINGS = DiscoverySettings()
