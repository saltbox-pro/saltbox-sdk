# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added

- Add detailed key value information to `DuplicateKeyException` and log duplicate key details during database errors.
- Add `SortOrder` enum and update repository/service APIs to support sorting direction (`SortOrder`) for `get_list` and repository methods.
- Add `user` and `sender` fields to `EventBusBaseMessage` and add `task_id` to `RunTaskEventBusMessage`.
- Add `instance_id` to `DiscoverySettings` and make `DiscoveryClient` use it when publishing/constructing instance URLs.
- Add `exchange` argument to `send_rpc_message` and `send_message`, and add `broker` parameter to `get_faststream_app` to support flexible routing.
- Add RabbitMQ-based event bus integration and common scheduler logic for scheduled tasks.
- Add `ANONYMOUS_SHORT_USER`, `SYSTEM_USER` and `SYSTEM_SHORT_USER` constants for standardized system/user identifiers.
- Add `MongoQueryField` and `match_query` utility to support mongo-like query filtering in tests and services.
- Add a JSON validator utility to centralize JSON schema/validation checks.
- Add FastAPI metrics: error request counter, aggregated metrics, and merged method/route metric labels.
- Add initial Inventory-related types to support upcoming inventory persistence and typing.

### Changed

- Move default arguments into the `key` argument for `OPAConfig` and `GatewayEndpointConfig` to simplify configuration mapping.
- Simplify `OPAConfig` handling (see Removed) and introduce `get_opa_query` helper; update `DiscoveryClient` and callers to use the new OPA flow.
- Refactor configuration and discovery surface: introduce `server_outer_socket`, `server_scheme`, `server_ws_scheme`, `KeycloakSettings`, and more precise `DiscoverySettings`; update `DiscoveryClient` to construct URLs from configurable paths for docs, OpenAPI and health checks.
- Refactor exception handling and FastAPI utilities: consolidate exceptions, change `DuplicateKeyException` to return HTTP 400, add `SaltBoxBaseException.extra_fields`, and provide custom OpenAPI and HTTP exception handling.
- Set a default `redis_url` in `RedisSettings` to `redis://localhost:6379/0` to provide a sensible local default.
- Refactor `get_current_user` to read headers from the `Request` object and simplify auth header handling.
- Improve typing and overrides for `MongoBaseService.get_list()` and update sorting logic to use the new `SortOrder` type.
- Add `mongo_host` to `MongoSettings` and update logger configuration (`LoggerSettings.model_config`) to ignore extra fields.

### Fixed

- Raise a `ValueError` on invalid cursor values in `zscan` to prevent silent failures.
- Fix potential timestamps inconsistency in persistence logic to ensure stable ordering of time-based fields.
- Improve ObjectId conversion and exception handling in utility functions to avoid masking original errors.

### Removed

- Remove `include_object` field from `OPAConfig` schema to simplify OPA configuration and queries.
- Remove deprecated exception classes from the discovery client and consolidate error handling into unified exceptions.
- Remove leftover `saltbox_sdk.egg-info` artifacts and other obsolete files from the repository.
