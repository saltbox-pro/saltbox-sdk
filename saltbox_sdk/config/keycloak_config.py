import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(os.environ.get('SALTBOX_ENV_FILE', '.env'))


class KeycloakSettings(BaseSettings):
    server_url: str = ''
    front_url: str = ''
    realm: str = ''
    client: str = ''
    client_secret: str = ''

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_prefix='KEYCLOAK_', extra='ignore')

    @property
    def oidc_url(self) -> str:
        return f'{self.server_url}/realms/{self.realm}/.well-known/openid-configuration'

    @property
    def authorization_endpoint(self) -> str:
        return f'{self.front_url}/realms/{self.realm}/protocol/openid-connect/auth'

    @property
    def token_url(self) -> str:
        return f'{self.front_url}/realms/{self.realm}/protocol/openid-connect/token'


KC_SETTINGS = KeycloakSettings()
