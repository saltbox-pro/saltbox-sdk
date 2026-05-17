from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from saltbox_sdk.config.keycloak_config import KC_SETTINGS


def get_custom_openapi_schema(
    app_configs: dict[str, Any],
    routes: list,
    servers: list | None = None,
) -> dict:
    """Generate a custom OpenAPI schema for the FastAPI application.
    This function customizes the OpenAPI schema by adding security schemes,
    external documentation, and other relevant information.
    It uses the Keycloak OIDC configuration for OAuth2 authentication.

    Args:
        app_configs (dict): Application configuration settings.
        routes (list): List of FastAPI routes.
        servers (list): List of server configurations.
    Returns:
        dict: Custom OpenAPI schema.
    """
    oauth2_scheme = {
        'type': 'oauth2',
        'flows': {
            'authorizationCode': {
                'authorizationUrl': KC_SETTINGS.authorization_endpoint,
                'tokenUrl': KC_SETTINGS.token_url,
                'scopes': {'openid': 'OpenID Connect scope'},
            }
        },
    }

    openapi_schema = get_openapi(
        title=app_configs['title'],
        version=app_configs['version'],
        description=app_configs['description'],
        routes=routes,
        servers=servers or [],
    )
    openapi_schema['components']['securitySchemes'] = {'KeycloakOIDC': oauth2_scheme}
    openapi_schema['security'] = [{'KeycloakOIDC': []}]
    openapi_schema['externalDocs'] = {
        'description': 'Official Salt.Box documentation',
        'url': 'https://saltbox.pro',
    }

    return openapi_schema


def custom_openapi(
    app: FastAPI, app_config: dict[str, Any], servers: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    app.openapi_schema = get_custom_openapi_schema(
        app_configs=app_config,
        routes=app.routes,
        servers=servers,
    )
    return app.openapi_schema


def patch_swagger_config(app_config: dict[str, Any]) -> dict[str, Any]:
    """Patch the Swagger configuration with custom settings."""

    app_config['redoc_url'] = None
    app_config['swagger_ui_init_oauth'] = {
        'clientId': KC_SETTINGS.client,
        'clientSecret': KC_SETTINGS.client_secret,
        'scopes': 'openid',
    }
    app_config['swagger_ui_parameters'] = {
        'displayRequestDuration': True,
        'filter': True,
    }
    return app_config
