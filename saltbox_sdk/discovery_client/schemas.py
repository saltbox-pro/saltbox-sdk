from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProxyBalancingStrategy(StrEnum):
    RANDOM = 'rand'
    ROUND_ROBIN = 'rr'
    WEIGHTED_ROUND_ROBIN = 'wrr'


class ServiceType(StrEnum):
    OFFICIAL = 'official'
    THIRD_PARTY = 'third-party'


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str
    message: str | None = None


class OPAQueryFilterFormat(StrEnum):
    MONGO = 'mongo'
    SQL = 'sql'


class OPAConfig(BaseModel):
    """OPA configuration for service endpoints.

    Fields:
        action: One of resource actions defined in resource model (e.g., 'read', 'write')
        policy: OPA policy package name (e.g., 'core.collections')
        is_partial: Whether the Gateway should use partial evaluation for this endpoint
        partial_query: Policy statement for partial evaluation
        unknowns: List of unknowns to pass to OPA
        query_filter_format: Filter format returned by OPAClient
    """

    action: str = Field(serialization_alias='x-opa-action')
    policy: str = Field(default='public', serialization_alias='x-opa-policy')
    is_partial: bool = Field(serialization_alias='x-opa-partial', default=False)
    partial_query: str | None = Field(serialization_alias='x-opa-partial-query', default=None)
    unknowns: list[str] | None = Field(serialization_alias='x-opa-unknowns', default=None)
    query_filter_format: OPAQueryFilterFormat | None = Field(
        serialization_alias='x-opa-query-filter-format', default=None
    )

    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class GatewayEndpointConfig(OPAConfig):
    cache_ttl: int | None = Field(serialization_alias='x-cache-ttl', default=0)


class ServiceEndpoint(BaseModel):
    path: str
    method: str
    summary: str = ''
    description: str = ''
    opa_config: OPAConfig
    cache_ttl: int = 0


class ServiceStatus(StrEnum):
    RUNNING = 'running'
    STOPPED = 'stopped'
    ERROR = 'error'


class ServiceInstance(BaseModel):
    id: str
    host: str
    port: int
    base_route: str | None = None
    version: str | None = None
    endpoints: list[ServiceEndpoint] = []
    healthcheck_path: str | None = None
    docs_path: str | None = None
    openapi_path: str | None = None
    enabled: bool = False
    healthy: bool | None = None
    last_check: float | None = None
    last_healthy: float | None = None


class ServiceFrontendEnv(BaseModel):
    api_base_path: str | None = None
    ws_server_url: str | None = None


class ServiceFrontendConfig(BaseModel):
    service_name: str | None = None
    is_available: bool = False
    url: str
    static_host: str | None = None
    env: ServiceFrontendEnv | None = None


class ServiceSchema(BaseModel):
    name: str = Field(title='Service name', pattern=r'^[a-z0-9-]+$', min_length=3, max_length=30)
    title: str
    description: str
    vendor: str
    type: ServiceType
    instances: list[ServiceInstance]
    front_config: ServiceFrontendConfig
    enabled: bool = True
    load_balancing_strategy: ProxyBalancingStrategy = ProxyBalancingStrategy.RANDOM


class DiscoveryResponse(BaseModel):
    success: bool
    message: str
