<div align = right>

&ensp;[<kbd> <br> EN <br> </kbd>](./README.md)&ensp;
&ensp;[<kbd> <br> RU <br> </kbd>](./README_RU.md)&ensp;

</div>

---

# Salt.Box SDK

## Содержание

- **[Описание](#описание)**
- **[Установка с экстрами](#установка-с-экстрами)**
- **[Модули](#модули)**
- **[Разработка](#разработка)**


## Описание

**Salt.Box SDK** – общая библиотека, на которой построены backend-сервисы
Salt.Box, Core, Gateway и другие. В ней лежат классы, которые
иначе дублировались бы в каждом сервисе: pydantic-настройки для каждой
внешней зависимости, базовые репозитории MongoDB и Redis, клиент Discovery,
через который сервисы регистрируются в Gateway, событийная шина на
FastStream, middleware и настройка OpenAPI для FastAPI, универсальный
фреймворк миграций данных, и публикация событий аудита.

## Установка с экстрами

Большинство собственных зависимостей SDK опциональны и объявлены в
[`pyproject.toml`](./pyproject.toml) как экстры, так что потребитель sdk
подтягивает только то, что реально использует:

- `mongo` – [pymongo](https://pymongo.readthedocs.io/)
- `redis` – [redis-py](https://redis.readthedocs.io/)
- `rest` – [FastAPI](https://fastapi.tiangolo.com/)
- `event-bus` – [FastStream](https://faststream.airt.ai/) с RabbitMQ
- `taskiq` – [TaskIQ](https://taskiq-python.github.io/)
- `dev` – линтинг, типизация и pre-commit для разработки самого SDK

```bash
uv pip install "saltbox-sdk[mongo,rest]"
```

На практике потребляющие сервисы закрепляют эти же библиотеки прямо в
собственных requirements, а не через экстры, экстры в основном документируют,
какой части SDK какая библиотека нужна.

## Модули

- [`config`](./saltbox_sdk/config) – pydantic-настройки для каждой внешней
  зависимости: `MongoSettings`, `RedisSettings`, `RabbitSettings`,
  `KeycloakSettings`, `DiscoverySettings`, и конфигурация логгера
- [`db/mongo`](./saltbox_sdk/db/mongo) – singleton клиента MongoDB, базовые
  классы репозиториев и хелперы для агрегационных конвейеров
- [`db/redis`](./saltbox_sdk/db/redis) – конфигурация клиента Redis и
  базовый репозиторий sorted-set
- [`discovery_client`](./saltbox_sdk/discovery_client) – `DiscoveryClient`,
  который сервис использует при старте, чтобы зарегистрироваться в Gateway
  Discovery, он строит payload регистрации из собственной OpenAPI-схемы
  сервиса, включая эндпоинты, их аннотации политик `x-opa-*` и TTL кэша
- [`event_bus`](./saltbox_sdk/event_bus) – приложение и фабрика брокера
  FastStream над RabbitMQ, а также общие схемы сообщений событийной шины
- [`faststream_utils`](./saltbox_sdk/faststream_utils) – хелперы зависимостей
  для обработчиков FastStream
- [`fastapi_utils`](./saltbox_sdk/fastapi_utils) – хелперы CSV-экспорта,
  кастомная генерация OpenAPI, общие обработчики исключений, middleware
  `AuditContextMiddleware` и `ServerTimingMiddleware`, и экспортёр с
  агрегатором метрик Prometheus
- [`migrations`](./saltbox_sdk/migrations) – универсальный фреймворк
  миграций данных, `Migrator` находит подклассы `BaseMigration` в пакетах
  `migrations` настроенных модулей и выполняет их в порядке зависимостей
- [`scheduler`](./saltbox_sdk/scheduler) – общие схемы сообщений и логика
  обработчика для синхронизации запланированных шаблонов тасков и их запуска
  через событийную шину
- [`serivces`](./saltbox_sdk/serivces) – базовые классы сервисов,
  использующие репозитории из `db`: обычные, time-series и уведомляющие об
  изменениях сервисы Mongo, и сервис sorted-set для Redis
- [`utilities`](./saltbox_sdk/utilities) – `AuditEventPublisher` и хелпер
  `build_audit_event`, валидация JSON-схем, хелперы дополнительных данных
  миньонов, константы статусов и хелперы для TaskIQ

## Разработка

```bash
uv venv
source .venv/bin/activate
uv pip install -r pyproject.toml --all-extras -e .
```
