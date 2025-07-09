from enum import Enum

from pydantic import BaseModel, Field


class ProxyBalancingStrategy(str, Enum):
    RANDOM = 'rand'
    ROUND_ROBIN = 'rr'
    WEIGHTED_ROUND_ROBIN = 'wrr'


class ServiceType(str, Enum):
    OFFICIAL = 'official'
    THIRD_PARTY = 'third-party'


class HealthCheckResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: str
    message: str | None = None


class OPAQueryFilterFormat(str, Enum):
    MONGO = 'mongo'
    SQL = 'sql'


class OPAConfig(BaseModel):
    policy: str = 'public'
    is_partial: bool = False
    partial_query: str | None = None
    unknowns: list[str] | None = None
    query_filter_format: OPAQueryFilterFormat | None = None


class ServiceEndpoint(BaseModel):
    path: str
    method: str
    summary: str = ''
    description: str = ''
    opa_config: OPAConfig = Field(default_factory=OPAConfig)
    cache_ttl: int = 0


class ServiceStatus(str, Enum):
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
    health_check_path: str
    auto_discover_routes: bool = False
    enabled: bool = False
    healthy: bool | None = None
    last_check: float | None = None
    last_healthy: float | None = None


class ServiceFrontendEnv(BaseModel):
    api_base_path: str | None = None
    ws_server_url: str | None = None


class ServiceFrontendConfig(BaseModel):
    url: str
    static_host: str | None = None
    env: ServiceFrontendEnv | None = None


class ServiceSchema(BaseModel):
    name: str
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
