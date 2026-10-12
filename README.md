<div align = right>

&ensp;[<kbd> <br> EN <br> </kbd>](./README.md)&ensp;
&ensp;[<kbd> <br> RU <br> </kbd>](./README_RU.md)&ensp;

</div>

---

# Salt.Box SDK

## Table of Contents

- **[About](#about)**
- **[Installing with extras](#installing-with-extras)**
- **[Modules](#modules)**
- **[Development](#development)**


## About

**Salt.Box SDK** is the shared library behind Salt.Box's backend services,
Core, Gateway and others. It holds the building blocks that would otherwise
be duplicated across them: pydantic settings for every external dependency,
MongoDB and Redis repository bases, the Discovery client services use to
register themselves with Gateway, the FastStream-based event bus, FastAPI
middlewares and OpenAPI customization, a generic data migrations framework,
and audit event publishing.

## Installing with extras

Most of the SDK's own dependencies are optional, declared in
[`pyproject.toml`](./pyproject.toml) as extras, so a consumer only pulls in
what it actually uses:

- `mongo` – [pymongo](https://pymongo.readthedocs.io/)
- `redis` – [redis-py](https://redis.readthedocs.io/)
- `rest` – [FastAPI](https://fastapi.tiangolo.com/)
- `event-bus` – [FastStream](https://faststream.airt.ai/) with the RabbitMQ transport
- `taskiq` – [TaskIQ](https://taskiq-python.github.io/)
- `dev` – linting, typing and pre-commit tooling for developing the SDK itself

```bash
uv pip install "saltbox-sdk[mongo,rest]"
```

In practice consuming services pin these same libraries directly in their
own requirements rather than through the extras, the extras mainly document
which parts of the SDK need which library installed.

## Modules

- [`config`](./saltbox_sdk/config) – pydantic settings for every external
  dependency: `MongoSettings`, `RedisSettings`, `RabbitSettings`,
  `KeycloakSettings`, `DiscoverySettings`, and logger configuration
- [`db/mongo`](./saltbox_sdk/db/mongo) – the MongoDB client singleton, base
  repository classes, plain, time-series and tree-shaped, and aggregation
  pipeline helpers
- [`db/redis`](./saltbox_sdk/db/redis) – Redis client configuration and a
  sorted-set repository base
- [`discovery_client`](./saltbox_sdk/discovery_client) – `DiscoveryClient`,
  used by a service on startup to register itself with Gateway Discovery,
  it builds the registration payload from the service's own OpenAPI schema,
  endpoints, their `x-opa-*` policy annotations, and cache TTLs included
- [`event_bus`](./saltbox_sdk/event_bus) – a FastStream app and broker
  factory over RabbitMQ, plus the shared event-bus message schemas
- [`faststream_utils`](./saltbox_sdk/faststream_utils) – dependency helpers
  for FastStream handlers
- [`fastapi_utils`](./saltbox_sdk/fastapi_utils) – CSV export helpers,
  custom OpenAPI generation, shared exception handlers, the
  `AuditContextMiddleware` and `ServerTimingMiddleware` middlewares, and a
  Prometheus metrics exporter and aggregator
- [`migrations`](./saltbox_sdk/migrations) – a generic data migrations
  framework, `Migrator` discovers `BaseMigration` subclasses under the
  configured modules' `migrations` packages and runs them in dependency
  order
- [`scheduler`](./saltbox_sdk/scheduler) – shared message schemas and the
  handler logic for syncing scheduled task templates and running them over
  the event bus
- [`serivces`](./saltbox_sdk/serivces) – base service classes consuming the
  `db` repositories: plain, time-series and notify-on-change Mongo services,
  and a Redis sorted-set service
- [`utilities`](./saltbox_sdk/utilities) – the `AuditEventPublisher` and
  `build_audit_event` helper, JSON schema validation, minion extra data
  helpers, status constants, and TaskIQ helpers

## Development

```bash
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml --all-extras -e .
```
