import asyncio
import socket
import uuid
from pathlib import Path
from typing import Any

import httpx

from saltbox_sdk import __version__
from saltbox_sdk.config import SETTINGS, logger
from saltbox_sdk.discovery_client.schemas import (
    OPAConfig,
    ProxyBalancingStrategy,
    ServiceEndpoint,
    ServiceFrontendConfig,
    ServiceFrontendEnv,
    ServiceInstance,
    ServiceSchema,
)


class DiscoveryClient:
    def __init__(
        self,
        openapi_schema: dict[str, Any],
        httpx_client: httpx.AsyncClient | None = None,
    ):
        self._httpx_client = httpx_client or httpx.AsyncClient()
        self._openapi_schema = openapi_schema

    def __get_or_create_instance_id(self) -> str:
        file_path = (
            Path(__file__).parent.parent / f'data/{SETTINGS.service_name}_instance_{socket.gethostname()}_id.txt'
        )
        if Path.exists(file_path):
            with Path.open(file_path) as f:
                logger.debug('Using existing instance ID')
                return f.read().strip()
        instance_id = str(uuid.uuid4())
        with Path.open(file_path, 'w') as f:
            f.write(instance_id)
        logger.debug(f'Generated new instance ID: {instance_id}')
        return instance_id

    async def _get_endpoints_from_openapi(self) -> list[ServiceEndpoint]:
        endpoints = []
        for path, methods in self._openapi_schema.get('paths', {}).items():
            for method, details in methods.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    endpoints.append(
                        ServiceEndpoint(
                            path=path,
                            method=method.upper(),
                            summary=details.get('summary', ''),
                            description=details.get('description', ''),
                            opa_config=OPAConfig(
                                policy=details.get('x-opa-policy', 'public'),
                                is_partial=details.get('x-opa-partial', False),
                                partial_query=details.get('x-opa-partial-query', None),
                                unknowns=details.get('x-opa-unknowns', None),
                                query_filter_format=details.get('x-opa-query-filter-format', None),
                            ),
                            cache_ttl=details.get('x-cache-ttl', 0),
                        )
                    )

        return endpoints

    async def _create_service_object(self) -> ServiceSchema:
        """Creates a service object from the configuration."""
        endpoints = await self._get_endpoints_from_openapi()

        instance = ServiceInstance(
            id=self.__get_or_create_instance_id(),
            # host=DISCOVERY_CONFIG.instance_host,
            host=socket.gethostname(),
            port=SETTINGS.instance_port,
            base_route='',
            version=__version__,
            health_check_path='/discovery/health',
            auto_discover_routes=True,
            enabled=True,
            endpoints=endpoints,
        )

        front_config = ServiceFrontendConfig(
            url=f'{SETTINGS.base_url}/static/{SETTINGS.service_name}',
            static_host=f'http://{SETTINGS.front_container_name}:{SETTINGS.front_container_port}',
            env=ServiceFrontendEnv(
                api_base_path=f'{SETTINGS.base_url.strip("/")}/api/{SETTINGS.service_name}',
                ws_server_url=f'ws://{SETTINGS.base_url.removeprefix("http://").removesuffix("/")}/api/{SETTINGS.service_name}',
            ),
        )

        return ServiceSchema(
            name=SETTINGS.service_name,
            title=SETTINGS.service_title,
            description=SETTINGS.service_description,
            type=SETTINGS.service_type,
            vendor=SETTINGS.service_vendor,
            instances=[instance],
            enabled=True,
            load_balancing_strategy=ProxyBalancingStrategy.ROUND_ROBIN,
            front_config=front_config,
        )

    async def register(self) -> None:
        service = await self._create_service_object()
        registration_data = service.model_dump()
        logger.debug(f'Discovery URL: {SETTINGS.discovery_url}')

        while True:
            if not await self.check_discovery_service():
                logger.warning('Discovery service is unavailable, retrying in 5 seconds...')
                await asyncio.sleep(5)
                continue
            try:
                response = await self._httpx_client.post(
                    f'{SETTINGS.discovery_url}/register',
                    json=registration_data,
                    timeout=2.0,
                    headers={'Content-Type': 'application/json'},
                )
                if response.status_code == 200:
                    logger.info('Service registered successfully')
                    logger.debug(f'Instance Host: {registration_data["instances"][0]["host"]}')
                    break
                else:
                    logger.error(f'Failed to register service: {response.text}')
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f'Error during service registration: {e}')
                await asyncio.sleep(5)

    async def check_discovery_service(self) -> bool:
        """Проверяет доступность сервиса Discovery"""
        try:
            logger.debug('Checking Discovery service availability on %s/health', SETTINGS.discovery_url)
            response = await self._httpx_client.get(f'{SETTINGS.discovery_url}/health', timeout=2.0)
            return response.status_code == 200
        except Exception as e:
            logger.error(f'Error checking discovery service: {e}')
            return False
