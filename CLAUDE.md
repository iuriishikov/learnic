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
- FastAPI + uvicorn, `ORJSONResponse` as default
- Pydantic 2 — **only at the HTTP boundary** (routes), never in application/entities
- SQLAlchemy 2.0 async + psycopg 3, Alembic
- dishka for DI (`make_async_container`, `setup_dishka`, `FromDishka`, `DishkaRoute`)
- pytest + pytest-asyncio (auto mode), httpx for integration tests
- ruff (strict), mypy (strict), bandit, semgrep, codespell
- Package management: **Poetry** (see below)
- Task runner: `just`

Pinned versions live in `pyproject.toml`. Do not loosen pins without a reason.

## Package Management (Poetry)

Always use `poetry` commands. Do not mix `pip install`, `uv`, or raw
`requirements.txt` into instructions.

```bash
poetry install --with dev             # install everything for local dev
poetry install --only main            # prod only
poetry add <pkg>                      # add runtime dep
poetry add --group dev <pkg>          # add dev dep
poetry add --group test <pkg>         # add test dep
poetry remove <pkg>
poetry run <cmd>                      # run inside venv
poetry shell                          # activate venv
poetry lock --no-update               # refresh lock without bumping
```

Dependency groups are declared under `[tool.poetry.dependencies]` and
`[tool.poetry.group.*.dependencies]`. When adding a dependency, always commit
the updated `poetry.lock`.

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
  - `common/` — `BaseEntity[OIDType]`, `DomainError`, `FieldError` base classes
  - `<aggregate>/` — `models.py` (entity), `value_objects.py` (VOs with invariants
    enforced in `__post_init__`), `errors.py` (FieldError subclasses)

- `src/<project>/application/` — use cases + persistence protocols. Knows nothing
  about FastAPI, SQLAlchemy, or dishka.
  - `commands/<aggregate>/` — write-side handlers (`*CommandHandler`)
  - `queries/<aggregate>/` — read-side handlers (`*QueryHandler`)
  - `common/persistence/` — `Protocol`-based gateways and readers; view models
  - `common/errors/` — `ApplicationError`, `EntityNotFoundError`, and other
    application-layer errors
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
  - `configs.py` — `NamedTuple`-based configs

- `src/<project>/presentation/http/v<N>/` — FastAPI routes, Pydantic schemas,
  exception handlers. Routes convert schemas to command/query DTOs and delegate
  to handlers.

- `src/<project>/bootstrap.py` — wiring functions: `setup_configs`,
  `setup_routes`, `setup_middlewares`, `setup_exc_handlers`, `setup_map_tables`,
  `setup_observability`.

- `src/<project>/ioc.py` — dishka providers (`configs_provider`, `db_provider`,
  `gateways_provider`, `interactors_provider`, `setup_providers`).

- `src/<project>/web.py` — `create_app_tests()` and `create_app_production()`
  entry points.

- `src/<project>/__main__.py` — runs the production app via uvicorn.

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
   new entities via `@classmethod create_<n>(...)` that passes
   `cast("<IDType>", cast("object", None))` as a placeholder `oid` — the real
   ID is assigned by the DB on flush.

7. **Imperative SQLAlchemy mapping.** Mapping functions (e.g. `map_user_table()`)
   must be called once at startup via `setup_map_tables()`. Do not introduce
   declarative `DeclarativeBase` models — entities must remain ORM-free.

8. **DI registration**:
   - Use cases are registered in `ioc.interactors_provider` via
     `provider.provide_all(...)`. When adding a handler, add it to that list.
   - Gateways/readers are registered in `gateways_provider` with explicit
     `provides=<Protocol>` (e.g. `provider.provide(UserMapperAlchemy, provides=UserGateway)`).

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
- `NewType` for typed IDs: `UserID = NewType("UserID", int)`.
- Commands/queries: `@dataclass(slots=True, frozen=True)`.
- Value objects: `@dataclass(slots=True, frozen=True, eq=True, unsafe_hash=True)`.
- Async for all I/O.
- Timestamps in tables: `server_default=sa.func.now()`, and for `updated_at`
  also `onupdate=sa.func.now(), server_onupdate=sa.func.now()`.
- In application code, prefer `datetime.now(timezone.utc)` — never `utcnow()` (deprecated, naive).

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
from dataclasses import dataclass
from typing import NewType, cast
from typing_extensions import Self

from <project>.entities.common.base_entity import BaseEntity

<Aggregate>ID = NewType("<Aggregate>ID", int)

@dataclass
class <Aggregate>(BaseEntity[<Aggregate>ID]):
    <field>: <VO>
    # ... other fields

    def change_<field>(self, new_value: <VO>) -> None:
        self.<field> = new_value

    @classmethod
    def create_<aggregate>(cls, <args>) -> Self:
        return cls(
            oid=cast("<Aggregate>ID", cast("object", None)),
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
    return await interactor.run(command_data)
```

### Exception handler mapping

Domain `FieldError` → 422; application `EntityNotFoundError` → 404;
generic `Exception` → 500. Mapping lives in
`presentation/http/v<N>/common/exc_handlers.py::map_exc_handlers(app)`.
**Do not raise `HTTPException` from handlers** — raise domain/application
errors instead, let the exception handlers translate them.

## Adding a new use case (checklist)

1. Create the DTO and handler in `application/{commands,queries}/<aggregate>/<n>.py`.
2. Implement the handler class with `@final`, `.run(data)`, deps via `__init__`.
3. If new persistence methods are needed:
   - extend the relevant `Protocol` in `application/common/persistence/<aggregate>.py`
   - implement in `infrastructure/persistence/adapters/<aggregate>.py` with `@override`
4. **Register the handler** in `ioc.interactors_provider` — add it to `provide_all(...)`.
5. Expose via a route in `presentation/http/v<N>/routes/<aggregate>.py`, using
   a Pydantic schema for input validation if needed. Use `FromDishka[Handler]`.
6. Map any new domain errors to HTTP codes in `exc_handlers.py`.
7. Unit test in `tests/unit/application/...` using Mock-based fixtures
   (see `tests/unit/application/conftest.py` for the pattern).
8. Integration test in `tests/integrations/http/v<N>/...` if the route is new.

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

```bash
just bootstrap      # copy .env.dist to .env, install deps, install pre-commit
just venv-sync      # poetry install --with dev
just serve          # alembic upgrade head && python -m <project>
just lint           # ruff check + ruff format + codespell
just static         # mypy + bandit + semgrep
just pre-commit     # run all pre-commit hooks
just test           # spin up dev DB, run pytest -x --ff, tear down
just test-cov       # test + coverage report
just dev-up / dev-down
just prod-up / prod-down
```

## Anti-patterns (do not do this)

- ❌ Import `fastapi`, `sqlalchemy`, `pydantic`, `dishka` inside `entities/`
  or `application/`.
- ❌ Put business logic in routes. Routes build DTOs and call `interactor.run(...)`.
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

## Environment & configuration

Configs are `NamedTuple`s in `infrastructure/configs.py` (`PostgresConfig`,
`ASGIConfig`, `ObservabilityConfig`, `Configs`). Values are read from env vars
in `bootstrap.setup_configs()`. `.env.dist` is the template; `just bootstrap`
copies it to `.env`.

Typical required env vars:
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`,
`POSTGRES_DB`, `SQLALCHEMY_DEBUG`, `UVICORN_HOST`, `UVICORN_PORT`.

Optional: `FASTAPI_DEBUG`, `APP_NAME`, `GRPC_ENDPOINT` (observability).

## Git & commits

- Git-flow-next: `main` = production, `develop` = integration.
- Conventional Commits: `feat(<aggregate>): ...`, `fix(api): ...`, `chore: ...`,
  `test(<aggregate>): ...`, `refactor(persistence): ...`.
- Feature branches for real features. Scaffolding/infrastructure work can go
  directly to `develop` when working solo.

## When unsure

If a change would require breaking any rule above — stop and ask, don't paper
over it. The architectural strictness is the point of this codebase.