# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added

- Add `title`, `description`, `icon` and `is_single_item` to `MinionExtraDataCategory`.
- Add `mongo_uri` to `MongoSettings` to override the built connection URL.
- Allow comma-separated list of hosts (with optional `:port`) in `mongo_host`.
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
- Add data migrations framework and related migration types.
- Add mongo transactions support, including session and transaction helpers.
- Add mongo base service with notification.
- Add `EmptyModel`.
- Add `Source` base model.
- Add `SaltBoxBaseException.get_extra_fields()` helper.
- Add `QueryParams` and `SortParams` schemas.
- Add common aggregation stage classes.
- Add joins support in mongo repositories.
- Add `get_tree` to `BaseTreeMongoRepository`.
- Add method to retrieve ancestor IDs for a target.
- Add logic to create mongo collections.
- Add updating mongo document by `find_one_and_update`.
- Add `projection_model` to `prepare_object_data` in `BaseMongoRepository`.
- Add `is_available` field to `ServiceFrontendConfig`.
- Add `is_external` flag to `DiscoverySettings`.
- Add `instance_base_route` to `DiscoverySettings`.
- Add merge guard to prevent unintended merges.

### Changed

- Pass mongo credentials to the client as `username`/`password` arguments instead of embedding them in the connection URL.
- Move default arguments into the `key` argument for `OPAConfig` and `GatewayEndpointConfig` to simplify configuration mapping.
- Simplify `OPAConfig` handling (see Removed) and introduce `get_opa_query` helper; update `DiscoveryClient` and callers to use the new OPA flow.
- Refactor configuration and discovery surface: introduce `server_outer_socket`, `server_scheme`, `server_ws_scheme`, `KeycloakSettings`, and more precise `DiscoverySettings`; update `DiscoveryClient` to construct URLs from configurable paths for docs, OpenAPI and health checks.
- Refactor exception handling and FastAPI utilities: consolidate exceptions, change `DuplicateKeyException` to return HTTP 400, add `SaltBoxBaseException.extra_fields`, and provide custom OpenAPI and HTTP exception handling.
- Set a default `redis_url` in `RedisSettings` to `redis://localhost:6379/0` to provide a sensible local default.
- Refactor `get_current_user` to read headers from the `Request` object and simplify auth header handling.
- Improve typing and overrides for `MongoBaseService.get_list()` and update sorting logic to use the new `SortOrder` type.
- Add `mongo_host` to `MongoSettings` and update logger configuration (`LoggerSettings.model_config`) to ignore extra fields.
- Refactor MongoDB client retrieval, singleton behavior, and session management.
- Add an option to allow MongoDB `replicaSet` to be unset in configuration.
- Refactor mongo repository joins.
- Refactor query preparation and improve readability.
- Use mongo pipelines in `count` and `exists` in `BaseMongoRepository` when applicable.
- Add recursion to `BaseMongoRepository._get_projection_from_model`.
- Refactor MongoDB imports and remove unused aliases.
- Update sortedset repository base class.
- Refactor `DiscoveryClient` to manage `httpx` client lifecycle.
- Update CI stages due to `ci-lib` changes.
- Add explanation/documentation for mongo internals.
- Update typing for `data` argument of service `create` methods to `dict`.
- Add migration stages for mongo collections.

### Fixed

- Raise a `ValueError` on invalid cursor values in `zscan` to prevent silent failures.
- Fix potential timestamps inconsistency in persistence logic to ensure stable ordering of time-based fields.
- Improve ObjectId conversion and exception handling in utility functions to avoid masking original errors.
- Fix `repo.count()` optimization.
- Handle `ObjectNotFoundException` in `get_parent_id`.
- Fix preparing mongo query when a value is `None`.
- Fix `MongoBaseService.get_list` interface.
- Fix `prepare_pipeline` method naming.
- Fix sorting on aggregated requests to mongo.
- Fix `exists` in mongo repositories.
- Fix `__prepare_query__` and `update` on `BaseMongoRepository`.
- Fix method signatures in services.
- Fix host assignment in service object creation.
- Fix ObjectId import handling in `exception_handlers.py`.
- Fix PEP 639 compliance.

### Removed

- Remove `include_object` field from `OPAConfig` schema to simplify OPA configuration and queries.
- Remove deprecated exception classes from the discovery client and consolidate error handling into unified exceptions.
- Remove leftover `saltbox_sdk.egg-info` artifacts and other obsolete files from the repository.
