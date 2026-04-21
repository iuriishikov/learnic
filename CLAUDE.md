# CLAUDE.md

This file guides Claude when working on this codebase. Read it first before
writing any code.

The project follows **Clean Architecture** (Uncle Bob) with strict layer
separation, CQRS for persistence, and imperative SQLAlchemy mapping. The
architectural rules below are non-negotiable — they are the reason this
codebase exists in its current shape. When in doubt, prefer the stricter,
more decoupled solution.

Replace `<project>` below with your actual package name (e.g. `shop`, `auth`).

## Project Overview

<Fill in 2–3 sentences: what this service does, who the users are, what the
domain is about. Example: "Backend for a subscription billing system. Users are
SMB customers (1–50 seats per tenant). Core domain: plans, subscriptions,
invoices, payments.">

## Tech Stack

- Python `>=3.10` (use `X | Y`, `list[T]`, `dict[K, V]`; no `from __future__ import annotations`)
- FastAPI + uvicorn — FastAPI serializes responses via Pydantic directly to JSON bytes; no `ORJSONResponse` needed.
  **All route handlers and anything they transitively touch are `async def`** —
  no sync route handlers, no sync dependencies, no blocking I/O on the event
  loop. If a third-party lib is sync-only, isolate it behind
  `asyncio.to_thread(...)` or `anyio.to_thread.run_sync(...)` in an adapter.
- Pydantic 2 — **only at the HTTP boundary** (routes) and **configuration** (`BaseSettings`), never in application/entities
- pydantic-settings — configuration via `BaseSettings` subclasses in `infrastructure/configs.py`; reads from env vars and `.env` file automatically; never use `os.environ` directly for config
- **Database: PostgreSQL EXCLUSIVELY** — SQLAlchemy 2.0 async for the app,
  Alembic for migrations. No MySQL, no SQLite (not even for tests), no MSSQL,
  no Oracle.
  - **Application path (async):** driver is `asyncpg`; URL scheme
    `postgresql+asyncpg://…`; engine built via `create_async_engine(...)`;
    sessions are `AsyncSession`; gateways/readers `await` everything.
  - **Migration path (sync):** Alembic runs synchronously with `psycopg` 3
    driver; URL scheme `postgresql+psycopg://…`; `env.py` uses
    `engine_from_config(...)` (sync). **Do not** try to drive Alembic via
    asyncpg — keep it sync, it's simpler and matches Alembic's default flow.
  - Both drivers are pinned in `pyproject.toml` runtime dependencies. The two
    DSN properties live on `PostgresConfig` (e.g. `dsn_async` / `dsn_sync`) —
    never hardcode a URL elsewhere.
  - Table types may use PostgreSQL-specific features (`sa.Uuid`, `JSONB`,
    arrays, `ON CONFLICT`) freely — portability is not a goal.
- dishka for DI (`make_async_container`, `setup_dishka`, `FromDishka`, `DishkaRoute`)
- **TaskIQ + Redis** for background tasks — `taskiq-redis` broker (`ListQueueBroker`)
  + `RedisAsyncResultBackend`. The producer side (FastAPI) talks to the broker
  through a `TaskScheduler` Protocol; the consumer side is a separate process
  (`poetry run taskiq worker learnic.worker:broker`). Never run the worker inside
  the API process in production — it would block the event loop and break
  independent scaling.
- **Object storage: S3-compatible** (`aioboto3`) — application code uses a
  `FileStorage` Protocol, infrastructure implements it via `S3FileStorage`
  (MinIO locally, any S3-compatible service in prod). All calls are async.
- pytest + pytest-asyncio (auto mode), httpx for integration tests
- ruff (strict), mypy (strict via `[tool.mypy]` with `strict = true` and
  `plugins = ["pydantic.mypy"]`), bandit, semgrep, codespell
- Package management: **Poetry** (see below)
- Task runner: `just`

Pinned versions live in `pyproject.toml`. Do not loosen pins without a reason.

## Package Management (Poetry 2.x)

Always use `poetry` commands. Do not mix `pip install`, `uv`, or raw
`requirements.txt` into instructions. This project uses Poetry 2.x conventions —
PEP 621 for dependencies, PEP 735 for dependency groups.

### pyproject.toml layout (Poetry 2.x)

Main (runtime) dependencies go under `[project]` (PEP 621):

```toml
[project]
name = "<project>"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "fastapi (>=0.119,<0.120)",
    "sqlalchemy[asyncio] (>=2.0,<3.0)",
    # ...
]
```

Dev / test / lint dependencies go under `[dependency-groups]` (PEP 735):

```toml
[dependency-groups]
test = [
    "pytest (>=8.0,<9.0)",
    "pytest-asyncio (>=1.0,<2.0)",
    "httpx (>=0.28,<0.29)",
]
lint = [
    "ruff (>=0.14,<0.15)",
    "mypy (>=1.18,<2.0)",
]
dev = [
    { include-group = "test" },
    { include-group = "lint" },
    "pre-commit (>=4.0,<5.0)",
]
```

Legacy `[tool.poetry.dependencies]` / `[tool.poetry.group.*.dependencies]`
still work, but prefer PEP 621 / PEP 735 in new projects.

### Day-to-day commands

```bash
poetry install                        # install main + non-optional groups
poetry install --with dev             # also include the `dev` optional group
poetry install --only main            # production-only: main group, nothing else
poetry install --only-root            # install project root only, no deps

poetry add <pkg>                      # add runtime dep (to main group)
poetry add -G dev <pkg>               # add dep to `dev` group (-G == --group)
poetry add -G test <pkg>
poetry remove <pkg>
poetry remove -G docs <pkg>

poetry sync                           # sync env to lock: removes anything not in lock
poetry sync --without dev             # prod-like sync
poetry lock                           # regenerate poetry.lock after editing pyproject
poetry lock --no-update               # refresh lock hashes without bumping versions

poetry run <cmd>                      # run a command inside the venv
poetry run pytest
poetry run alembic upgrade head
```

### Activating the virtual environment

**`poetry shell` no longer exists** in Poetry 2.x — it was extracted to the
separate `poetry-plugin-shell` plugin. The recommended way is `poetry env activate`,
which **prints** the activation command; you feed it to `eval` in your shell:

```bash
# Bash / Zsh
eval $(poetry env activate)

# Fish
eval (poetry env activate)

# PowerShell
Invoke-Expression (poetry env activate)
```

Most of the time you do not need to activate at all — `poetry run <cmd>` is
enough and composes better with CI, Docker, and `just` recipes.

### Environment management

```bash
poetry env use 3.12                   # pin the Python interpreter
poetry env use /full/path/to/python
poetry env use system                 # drop explicit activation
poetry env info                       # show info about the active venv
poetry env info --path                # just the venv path
poetry env info --executable          # just the Python executable path
poetry env list                       # list all venvs for this project
poetry env remove 3.12                # remove a specific venv
poetry env remove --all               # remove all venvs for this project
```

When adding a dependency, always commit the updated `poetry.lock`.

## Architecture

Clean Architecture. Dependencies flow **inward only**:

```
presentation ──▶ application ──▶ entities
                      ▲
infrastructure ───────┘   (implements application protocols)
```

### Layers and what lives where

- `src/<project>/entities/` — pure domain. Entities, value objects, domain errors.
  **Zero external imports.** Only stdlib + `typing_extensions`.
  - `common/` — `BaseEntity[OIDType]`, `ValueObject`, `DomainError`,
    `FieldError` base classes. `ValueObject` supplies
    `__composite_values__` so single- and multi-attribute VOs can be
    mapped through SQLAlchemy `composite()` without each VO restating
    the serializer; every concrete VO inherits from it.
  - `<aggregate>/` — `models.py` (entity), `value_objects.py` (VOs inherit
    from `ValueObject`; invariants enforced in `__post_init__`),
    `errors.py` (FieldError subclasses), `constants.py` (domain-level
    limits: max field lengths, bounded ranges, etc. — every magic number
    used inside VO invariants lives here as a `Final` constant, never
    inlined in `__post_init__`)

- `src/<project>/application/` — use cases + persistence protocols. Knows nothing
  about FastAPI, SQLAlchemy, dishka, TaskIQ, or boto3.
  - `commands/<aggregate>/` — write-side handlers (`*CommandHandler`)
  - `queries/<aggregate>/` — read-side handlers (`*QueryHandler`)
  - `common/persistence/` — `Protocol`-based gateways and readers; view models
  - `common/errors/` — `ApplicationError`, `EntityNotFoundError`, and other
    application-layer errors
  - `common/tasks/` — `TaskScheduler` Protocol. Add one method per background
    operation (`schedule_send_welcome_email(user_id)`, etc.). Handlers depend on
    this protocol, never on TaskIQ primitives.
  - `common/storage/` — `FileStorage` Protocol for object storage (put/get/
    delete/presigned URL). Handlers depend on this, never on boto3 directly.
  - `common/validators.py` — tiny pure helpers (e.g. `validate_empty`)

- `src/<project>/infrastructure/` — adapters. SQLAlchemy, configs, external APIs.
  - `persistence/adapters/` — implementations of application protocols
    (convention: suffix with `Alchemy` — `XxxMapperAlchemy`, `XxxReaderAlchemy`,
    `TransactionAlchemy`, `EntitySaverAlchemy`)
  - `persistence/models/` — **imperative** mapping via
    `mapper_registry.map_imperatively` (NOT declarative `DeclarativeBase`).
    Tables are defined as `sa.Table(...)`; entities are mapped later through
    `setup_map_tables()` at startup.
  - `persistence/alembic/` — migrations
  - `tasks/broker.py` — module-level `AsyncBroker` singleton. Every
    `@broker.task` decorator registers against this instance; both the FastAPI
    producer and the worker process import it.
  - `tasks/scheduler.py` — `TaskSchedulerTaskIQ` adapter: implements
    `TaskScheduler` by calling `<task>.kiq(...)` on the right handler.
  - `tasks/handlers/<aggregate>.py` — `@broker.task` functions. Keep them
    thin: `@inject` the relevant `CommandHandler` via `FromDishka[...]` and
    delegate to `handler.run(...)`. Business logic stays in the handler.
  - `storage/adapters/s3.py` — `S3FileStorage` implementing `FileStorage`.
  - `configs.py` — `BaseSettings` subclasses (`PostgresConfig`, `ASGIConfig`,
    `S3Config`, `TaskIQConfig`) aggregated by a `Configs` class.

- `src/<project>/presentation/http/` — FastAPI routes, Pydantic schemas,
  exception handlers. Routes convert schemas to command/query DTOs and delegate
  to handlers.

- `src/<project>/bootstrap.py` — wiring functions: `setup_configs`,
  `setup_routes`, `setup_middlewares`, `setup_exc_handlers`, `setup_map_tables`,
  `setup_observability`.

- `src/<project>/ioc.py` — dishka providers (`ConfigsProvider`, `DBProvider`,
  `GatewaysProvider`, `S3Provider`, `TasksProvider`, `InteractorsProvider`,
  `setup_providers`). When a new aggregate/task/storage target is added, the
  corresponding provider class gets the new `provide(...)`.

- `src/<project>/web.py` — `create_app_tests()` and `create_app_production()`
  FastAPI entry points. Manages TaskIQ broker lifecycle via FastAPI `lifespan`
  (`broker.startup()` / `broker.shutdown()`).

- `src/<project>/__main__.py` — runs the production API via `uvicorn.run(...)`
  with host/port from `ASGIConfig`.

- `src/<project>/worker.py` — TaskIQ worker entry point. Re-exports `broker`
  and wires dishka via `setup_dishka(container, broker=broker)`. Imports
  `infrastructure.tasks.handlers` to force `@broker.task` decorators to run
  before the worker starts consuming. Launch with
  `poetry run taskiq worker learnic.worker:broker`.

### Core rules (non-negotiable)

1. **Dependency rule**: `entities/` and `application/` must not import from
   `infrastructure/`, `presentation/`, FastAPI, SQLAlchemy, Pydantic, or dishka.
   Need infrastructure behavior inside the application? Define a `Protocol`
   in `application/common/persistence/` and implement it in `infrastructure/`.

2. **CQRS split per aggregate**:
   - `<Aggregate>Gateway` (write) returns domain entities
     (e.g. `UserGateway.with_id(id) -> User | None`)
   - `<Aggregate>Reader` (read) returns view models / DTOs
     (e.g. `UserReader.with_id(id) -> UserView | None`)
   - Never merge them. Read endpoints use Reader. Commands use Gateway.

3. **Handlers expose `.run(data)`**, not `__call__`. Keep this convention
   consistent across commands and queries.

4. **Transactions are managed in handlers**, via `Transaction` + `EntitySaver`
   protocols. Gateways and readers **never commit or flush**.

5. **Value objects validate in `__post_init__`** and raise `FieldError`
   subclasses. Domain invariants live in entities/VOs, not in handlers or routes.

6. **Entities use `BaseEntity[OIDType]`** with a single `oid` field. Construct
   new entities via `@classmethod create_<n>(...)` that generates the `oid`
   via `uuid.uuid4()` wrapped in the aggregate's `NewType`. IDs are produced in
   the domain, not by the database.

7. **Imperative SQLAlchemy mapping.** Mapping functions (e.g. `map_user_table()`)
   must be called once at startup via `setup_map_tables()`. Do not introduce
   declarative `DeclarativeBase` models — entities must remain ORM-free.
   Columns are plain SA types (`sa.String(MAX_LEN)`, `sa.Uuid`, etc.);
   VO ↔ primitive conversion lives in `properties={...}` via
   `composite(VO, table.c.col)` — never in custom `TypeDecorator`s.
   For **nullable** VO columns, pass a small factory function
   (`lambda v: VO(v) if v is not None else None`) instead of the VO
   class: SQLAlchemy 2.0 always instantiates the composite class on
   load, so the VO class itself would receive `None` and crash in
   `__post_init__`. (Obsoleted by `composite.return_none_on` in
   SQLAlchemy 2.1 once that ships.)

8. **DI registration**:
   - Use cases are registered in `ioc.interactors_provider` via
     `provider.provide_all(...)`. When adding a handler, add it to that list.
   - Gateways/readers are registered in `gateways_provider` with explicit
     `provides=<Protocol>` (e.g. `provider.provide(UserMapperAlchemy, provides=UserGateway)`).
   - Task schedulers are registered in `TasksProvider` the same way
     (`provider.provide(TaskSchedulerTaskIQ, provides=TaskScheduler)`).
   - Storage adapters go in `S3Provider` (`file_storage`, `FileStorage`).

9. **Background tasks**: the application layer only knows about `TaskScheduler`
   methods. Adding a new background operation means (a) adding a method to the
   Protocol, (b) adding the `@broker.task` function in
   `infrastructure/tasks/handlers/`, (c) implementing the scheduler method by
   calling `<task>.kiq(...)`. Tasks are thin: they resolve the `CommandHandler`
   via `FromDishka[...]` and delegate — business logic lives in the handler,
   not the task body.

10. **Producer/consumer process split**: FastAPI is the producer, `taskiq worker`
    is the consumer. They are separate OS processes (separate containers in
    prod). Do not run `Receiver.listen()` inside a FastAPI lifespan for
    production — it blocks the HTTP event loop and breaks independent scaling.
    In-process execution via `InMemoryBroker` is allowed ONLY when
    `TASKIQ_IN_MEMORY=true` is set (tests, throwaway local dev).

## Code Style

- Python 3.10+ syntax: `X | Y`, `list[T]`, `dict[K, V]`.
- **No `from __future__ import annotations`** — dishka and Pydantic rely on
  runtime-accessible annotations.
- `line-length = 79` (ruff).
- Strict mypy, strict ruff (`select = ["ALL"]` with a minimal ignore list).
- Type hints everywhere. Use `typing_extensions.override` when implementing a
  `Protocol` method.
- `Final` for injected dependencies stored as attributes.
- `@final` decorator on handler classes.
- **IDs are EXCLUSIVELY `uuid.UUID`** — never `int`, never auto-increment, never
  DB-generated sequences. Every aggregate ID must be a `NewType` wrapping
  `uuid.UUID`: `UserID = NewType("UserID", uuid.UUID)`. Generate new IDs in the
  domain via `uuid.uuid4()` inside `create_<aggregate>(...)` — not in
  handlers, not in adapters, not in the DB. Store as `sa.Uuid` in tables.
  No exceptions.
- `NewType` for typed IDs: `UserID = NewType("UserID", uuid.UUID)`.
- Commands/queries: `@dataclass(slots=True, frozen=True)`.
- Value objects: `@dataclass(slots=True, frozen=True, eq=True, unsafe_hash=True)`.
- Async for all I/O.
- Timestamps in tables: `server_default=sa.func.now()`, and for `updated_at`
  also `onupdate=sa.func.now(), server_onupdate=sa.func.now()`.
- In application code, prefer `datetime.now(timezone.utc)` — never `utcnow()` (deprecated, naive).
- **Docstring style: Google.** All docstrings in this codebase use Google-style
  sections (`Args:`, `Returns:`, `Raises:`, `Yields:`, `Examples:`) — no
  reST/Sphinx (`:param:` / `:returns:`), no NumPy-style underlines. Mixing
  styles inside one project breaks tool output (Sphinx, IDE hover, pydocstyle).
  Write the summary as a single imperative line; leave a blank line before any
  section.
- **Every HTTP route handler MUST have a Google-style docstring.** Routes are
  the public API surface — their docstrings feed directly into the OpenAPI
  schema and `/docs` (FastAPI uses the docstring as the operation
  `description`). Required sections:
  - One-line summary (becomes the OpenAPI `summary`).
  - `Args:` — every path/query/body/dependency parameter, what it means.
    Skip `interactor: FromDishka[...]` since it is not a public input.
  - `Returns:` — the response shape, in human terms (not just the type).
  - `Raises:` — every domain/application error the handler can propagate
    (e.g. `EntityNotFoundError`, `FieldError` subclasses), plus the HTTP
    status the exception handler maps it to.
  Docstrings on application handlers, gateways, readers, and entities are
  encouraged but optional. Docstrings on routes are non-negotiable.

## Canonical examples (copy these patterns)

### Value object with invariant

```python
from dataclasses import dataclass

@dataclass(slots=True, frozen=True, eq=True, unsafe_hash=True)
class <VO>:
    value: <primitive>

    def __post_init__(self) -> None:
        # enforce invariants; raise a FieldError subclass on violation
        if not <condition>:
            raise <FieldErrorSubclass>(<limit_or_context>)
```

### Entity

```python
import uuid
from dataclasses import dataclass
from typing import NewType
from typing_extensions import Self

from <project>.entities.common.base_entity import BaseEntity

<Aggregate>ID = NewType("<Aggregate>ID", uuid.UUID)

@dataclass
class <Aggregate>(BaseEntity[<Aggregate>ID]):
    <field>: <VO>
    # ... other fields

    def change_<field>(self, new_value: <VO>) -> None:
        self.<field> = new_value

    @classmethod
    def create_<aggregate>(cls, <args>) -> Self:
        return cls(
            oid=<Aggregate>ID(uuid.uuid4()),
            <field>=<args>,
        )
```

### Command handler (write side)

```python
from dataclasses import dataclass
from typing import final

from <project>.application.common.persistence.transaction import (
    EntitySaver, Transaction,
)
from <project>.application.common.persistence.<aggregate> import <Aggregate>Gateway

@dataclass(frozen=True, slots=True)
class <Action><Aggregate>Command:
    # plain primitive fields — the handler will wrap them into VOs
    <field>: <primitive>

@final
class <Action><Aggregate>CommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        <aggregate>_gateway: <Aggregate>Gateway,
    ) -> None:
        self._transaction = transaction
        self._entity_saver = entity_saver
        self._<aggregate>_gateway = <aggregate>_gateway

    async def run(self, data: <Action><Aggregate>Command) -> <ReturnType>:
        # 1. Load / construct domain objects via VOs + entities
        # 2. Mutate through entity methods
        # 3. Persist via entity_saver; commit via transaction
        self._entity_saver.add_one(<entity>)
        await self._transaction.commit()
        return <result>
```

### Query handler (read side)

```python
@final
class Get<Aggregate>QueryHandler:
    def __init__(self, reader: <Aggregate>Reader) -> None:
        self._reader = reader

    async def run(self, data: Get<Aggregate>Query) -> <AggregateOutput>:
        view = await self._reader.<method>(<args>)
        view = validate_empty(view, data.<id_field>)  # if single-item query
        return <AggregateOutput>(view)
```

### Persistence protocols

```python
from typing import Protocol

class <Aggregate>Gateway(Protocol):
    async def with_id(self, oid: <Aggregate>ID) -> <Aggregate> | None: ...
    # add mutation-adjacent lookups that return domain entities

class <Aggregate>Reader(Protocol):
    async def with_id(self, oid: <Aggregate>ID) -> <Aggregate>View | None: ...
    async def all(self, filters: <Filters>, pagination: Pagination) -> list[<Aggregate>View]: ...
    # add read-only queries returning view models
```

### Adapter

```python
from typing import Final
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

class <Aggregate>MapperAlchemy(<Aggregate>Gateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: <Aggregate>ID) -> <Aggregate> | None:
        stmt = select(<Aggregate>).where(<aggregate>_table.c.<id_col> == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()
```

### FastAPI route

```python
from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, status

router = APIRouter(
    prefix="/<aggregate>s",
    tags=["<Aggregate>"],
    route_class=DishkaRoute,  # no need for @inject on every handler
)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def add(
    command_data: <Action><Aggregate>Command,
    interactor: FromDishka[<Action><Aggregate>CommandHandler],
) -> <ReturnType>:
    """Create a new <aggregate>.

    Args:
        command_data: Payload describing the <aggregate> to create
            (validated by Pydantic at the HTTP boundary).

    Returns:
        The created <aggregate>'s identifier (or full view, as the
        handler defines).

    Raises:
        FieldError: One of the value-object invariants was violated;
            mapped to HTTP 422 by the global exception handler.
        EntityNotFoundError: A referenced related entity does not
            exist; mapped to HTTP 404.
    """
    return await interactor.run(command_data)
```

### Background task (TaskIQ)

Three files per new task: the Protocol method in application, the task body
in infrastructure, and the scheduler method wiring them together.

```python
# application/common/tasks/scheduler.py
from typing import Protocol

class TaskScheduler(Protocol):
    async def schedule_<action>(self, <id>: <AggregateID>) -> None: ...
```

```python
# infrastructure/tasks/handlers/<aggregate>.py
from dishka.integrations.taskiq import FromDishka, inject

from <project>.application.commands.<aggregate>.<action> import (
    <Action><Aggregate>Command,
    <Action><Aggregate>CommandHandler,
)
from <project>.infrastructure.tasks.broker import broker


@broker.task
@inject
async def <action>_<aggregate>_task(
    <id>: <AggregateID>,
    handler: FromDishka[<Action><Aggregate>CommandHandler],
) -> None:
    await handler.run(<Action><Aggregate>Command(<id>=<id>))
```

```python
# infrastructure/tasks/scheduler.py
from typing_extensions import override

from <project>.application.common.tasks.scheduler import TaskScheduler
from <project>.infrastructure.tasks.handlers.<aggregate> import (
    <action>_<aggregate>_task,
)


class TaskSchedulerTaskIQ(TaskScheduler):
    @override
    async def schedule_<action>(self, <id>: <AggregateID>) -> None:
        await <action>_<aggregate>_task.kiq(<id>)
```

### Exception handler mapping

Domain `FieldError` → 422; application `EntityNotFoundError` → 404;
generic `Exception` → 500. Mapping lives in
`presentation/http/common/exc_handlers.py::map_exc_handlers(app)`.
**Do not raise `HTTPException` from handlers** — raise domain/application
errors instead, let the exception handlers translate them.

## Adding a new use case (checklist)

1. Create the DTO and handler in `application/{commands,queries}/<aggregate>/<n>.py`.
2. Implement the handler class with `@final`, `.run(data)`, deps via `__init__`.
3. If new persistence methods are needed:
   - extend the relevant `Protocol` in `application/common/persistence/<aggregate>.py`
   - implement in `infrastructure/persistence/adapters/<aggregate>.py` with `@override`
4. **Register the handler** in `ioc.interactors_provider` — add it to `provide_all(...)`.
5. Expose via a route in `presentation/http/routes/<aggregate>.py`, using
   a Pydantic schema for input validation if needed. Use `FromDishka[Handler]`.
6. Map any new domain errors to HTTP codes in `exc_handlers.py`.
7. Unit test in `tests/unit/application/...` using Mock-based fixtures
   (see `tests/unit/application/conftest.py` for the pattern).
8. Integration test in `tests/integrations/http/...` if the route is new.

## Adding a new aggregate (checklist)

Beyond the use-case checklist, also:

1. `entities/<aggregate>/` with `models.py`, `value_objects.py`, `errors.py`, `__init__.py`.
2. `application/common/persistence/<aggregate>.py` with `Gateway` and `Reader` protocols
   and any view models / filters specific to the aggregate.
3. `infrastructure/persistence/models/<aggregate>.py` with `sa.Table` + `map_<aggregate>_table()`.
4. Call the new `map_<aggregate>_table()` inside `bootstrap.setup_map_tables()`.
5. `infrastructure/persistence/adapters/<aggregate>.py` with `*MapperAlchemy` + `*ReaderAlchemy`.
6. Register mapper + reader in `ioc.gateways_provider` with explicit `provides=...`.
7. Alembic: `poetry run alembic revision --autogenerate -m "add <aggregate>"`,
   then `poetry run alembic upgrade head`.

## Testing

- Unit tests in `tests/unit/`, integration in `tests/integrations/`.
- `pytest-asyncio` in auto mode — just write `async def test_...`.
- **Unit tests for handlers do not use dishka.** Construct the handler manually
  and pass `Mock`/`AsyncMock` dependencies. Keep shared fake fixtures
  (`fake_transaction`, `fake_entity_saver`, `fake_<aggregate>_gateway`,
  `fake_<aggregate>_reader`) in `tests/unit/application/conftest.py`.
- Unit tests for entities/VOs go in `tests/unit/entities/`, verifying
  invariants by asserting that invalid values raise the expected `FieldError`.
- Integration tests use `httpx.AsyncClient` against `create_app_tests()`;
  spin up DB via docker-compose.dev; create/drop tables per session.
- Test naming: `test_<what>_<condition>`. Use `@pytest.mark.parametrize` for cases.
- Prefer `assert_called_once`, `assert_called_once_with` over loose `.called`.

## Commands (justfile)

Recipes wrap Poetry commands to avoid remembering flags. Inside recipes,
prefer `poetry run <cmd>` over activating the venv — it's explicit and works
the same in local shells, Docker, and CI.

```bash
just bootstrap      # copy .env.dist to .env, poetry install
just serve          # dev-up, alembic upgrade head, then uvicorn + taskiq worker in parallel
just worker         # run the TaskIQ worker only (debugging tasks without the API)
just lint           # poetry run ruff check + ruff format + codespell
just static         # poetry run mypy + bandit + semgrep
just dev-up         # bring up Postgres, MinIO, Redis via docker-compose.dev
just dev-down       # tear down dev containers
just prod-up        # docker compose up for the full production-like stack
just prod-down      # tear down the production-like stack
```

`just serve` is the single daily-use recipe: it boots the dev dependencies,
applies migrations, and runs API + worker together with `--reload` on both.
Keep heavy/rare operations (tests, coverage) as ad-hoc `poetry run ...` calls
until the test suite grows enough to justify a dedicated recipe again.

Inside a recipe, prefer:

```just
@test:
    poetry run pytest -x --ff
```

over manual venv activation. If you need an interactive shell with the venv
on PATH, run `eval $(poetry env activate)` once in your terminal.

## Anti-patterns (do not do this)

- ❌ Import `fastapi`, `sqlalchemy`, `pydantic`, `dishka` inside `entities/`
  or `application/`.
- ❌ Put business logic in routes. Routes build DTOs and call `interactor.run(...)`.
- ❌ Write sync route handlers or sync use-case handlers. FastAPI is async-only
  here: every route is `async def`, every handler's `run(...)` is `async def`,
  every gateway/reader/adapter method is `async def`. If you must call a
  blocking sync library, wrap it in `asyncio.to_thread(...)` /
  `anyio.to_thread.run_sync(...)` inside an infrastructure adapter —
  never on the event loop directly.
- ❌ Use the sync `psycopg` driver for application code, or try to run Alembic
  through `asyncpg`. The split is: **app → asyncpg (async)**,
  **Alembic → psycopg (sync)**. Don't mix.
- ❌ Return Pydantic models from application handlers. Use dataclasses / `NamedTuple`.
- ❌ Raise `HTTPException` from handlers. Raise domain/application errors;
  let `exc_handlers.py` translate them.
- ❌ Call `session.commit()` / `session.flush()` from gateways or readers.
  Only `TransactionAlchemy` manages transactions.
- ❌ Merge `Gateway` and `Reader` into one protocol. The CQRS split is load-bearing.
- ❌ Introduce declarative SQLAlchemy base classes. This project uses imperative
  mapping to keep `entities/` free of ORM leakage.
- ❌ Forget to register new handlers in `ioc.interactors_provider.provide_all(...)`.
- ❌ Forget to call new `map_<aggregate>_table()` in `bootstrap.setup_map_tables()`.
- ❌ Use `datetime.utcnow()` (deprecated, naive). Prefer `datetime.now(timezone.utc)`
  or `sa.func.now()` in tables.
- ❌ Add `from __future__ import annotations` — breaks runtime annotation usage
  in dishka and Pydantic.
- ❌ Silently catch `DomainError` / `ApplicationError` in routes — let them propagate
  to the exception handlers.
- ❌ Swap PostgreSQL for another database (SQLite, MySQL, Oracle, MSSQL),
  even "just for tests" or "just for local dev". Use a real PostgreSQL
  instance — via `docker-compose.dev` locally, a dedicated test DB in CI.
- ❌ Inline magic numbers (max lengths, bounded ranges, etc.) inside VO
  `__post_init__` or entity methods. They live in the aggregate's
  `constants.py` as `Final` values and are imported by the VOs and any
  adapter that needs the same limit (e.g. `sa.String(FIRST_NAME_MAX_LEN)`).
- ❌ Read config values with `os.environ` directly — use `BaseSettings` subclasses
  in `infrastructure/configs.py`; pydantic-settings handles parsing and validation.
- ❌ Use `poetry shell` — it was removed from core in Poetry 2.x. Use
  `poetry run <cmd>` in recipes/CI, or `eval $(poetry env activate)` for an
  interactive shell.
- ❌ Put runtime dependencies under `[tool.poetry.dependencies]` in new code —
  use PEP 621 `[project].dependencies` instead. Same for groups: prefer
  `[dependency-groups]` (PEP 735) over `[tool.poetry.group.*]`.
- ❌ Use `poetry install --sync` (deprecated flag). Use the standalone
  `poetry sync` command.
- ❌ Import TaskIQ primitives (`AsyncBroker`, `.kiq`, `taskiq_redis`) from
  `application/`. Applications talk to the scheduler **only** through the
  `TaskScheduler` Protocol.
- ❌ Import `aioboto3` / `aiobotocore` from `application/` or `entities/`.
  Use the `FileStorage` Protocol; the S3 adapter is the only place that
  knows about boto3.
- ❌ Put business logic inside a `@broker.task` function. Tasks resolve the
  relevant `CommandHandler` via `FromDishka[...]` and delegate — if you
  find yourself writing SQL or validation inside a task, move it into a
  command handler first.
- ❌ Run the TaskIQ worker inside the FastAPI process in production
  (`asyncio.create_task(Receiver(broker).listen())` in a lifespan, or any
  equivalent). It steals the HTTP event loop and breaks horizontal scaling.
  The `InMemoryBroker` escape hatch exists strictly for tests and one-off
  local runs — gated by `TASKIQ_IN_MEMORY=true`.
- ❌ Hardcode broker/host/port defaults that only work in one environment
  (e.g. `host: str = "0.0.0.0"` for uvicorn). Required env values have no
  default in `BaseSettings`; defaulting in code forces every other
  environment to override it.

## Environment & configuration

Configs are `BaseSettings` subclasses in `infrastructure/configs.py`
(`PostgresConfig`, `ASGIConfig`, `S3Config`, `TaskIQConfig`). Each class
declares its env-var prefix via
`SettingsConfigDict(env_prefix="...", env_file=".env")` and pydantic-settings
reads + validates values automatically — **never use `os.environ` directly**.
`Configs` is a plain class that aggregates them; `load_configs()` instantiates
each `BaseSettings` subclass with no arguments.

`PostgresConfig` exposes two DSN properties — same host/port/user/password,
different drivers:

- `dsn_async` → `postgresql+asyncpg://…` for the app (`create_async_engine`).
- `dsn_sync`  → `postgresql+psycopg://…`  for Alembic (`engine_from_config`).

The app wiring (`ioc.db_provider`) must use `dsn_async`; Alembic's `env.py`
must use `dsn_sync`. Anything else is a configuration error.

`.env.dist` is the template; `just bootstrap` copies it to `.env`.

Required env vars (no code defaults — set them or startup fails):

- **Postgres**: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
  `POSTGRES_PORT`, `POSTGRES_DB`, `SQLALCHEMY_DEBUG`.
- **Uvicorn**: `UVICORN_HOST`, `UVICORN_PORT` (no defaults — deploys must
  declare the binding explicitly; Docker sets `0.0.0.0`, bare metal sets
  whatever is safe for that machine).
- **S3 / object storage**: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
  `S3_BUCKET`, `S3_REGION`.

Optional / pre-filled defaults:

- **TaskIQ**: `TASKIQ_BROKER_URL` (default `redis://localhost:6379/0`),
  `TASKIQ_RESULT_BACKEND_URL` (default `redis://localhost:6379/1`),
  `TASKIQ_IN_MEMORY` (default `false` — set `true` only in tests / throwaway
  local runs to swap the Redis broker for `InMemoryBroker`),
  `TASKIQ_WORKERS` (default `2` — number of worker subprocesses; ignored in
  local dev because `--reload` forces 1 worker).
- **FastAPI**: `FASTAPI_DEBUG`, `APP_NAME`, `GRPC_ENDPOINT` (observability).

## Git & commits

- Git-flow-next: `main` = production, `develop` = integration.
- Conventional Commits: `feat(<aggregate>): ...`, `fix(api): ...`, `chore: ...`,
  `test(<aggregate>): ...`, `refactor(persistence): ...`.
- Feature branches for real features. Scaffolding/infrastructure work can go
  directly to `develop` when working solo.

## When unsure

If a change would require breaking any rule above — stop and ask, don't paper
over it. The architectural strictness is the point of this codebase.