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
- dishka for DI (`make_async_container`, `setup_dishka`, `FromDishka`) — routes use
  a custom `DishkaErrorAwareRoute` class (see below) that combines dishka's
  auto-inject with `fastapi-error-map` per-route error maps. Do **not** use
  bare `DishkaRoute` in new routes.
- **fastapi-error-map** for HTTP error responses — per-route `error_map={ExceptionType: RULE}`
  declares which domain/application exceptions translate to which status codes, and
  auto-populates OpenAPI. Translators live in `presentation/http/common/errors/translators.py`,
  reusable rule constants in `presentation/http/common/errors/rules.py`. There is no
  global `exc_handlers.py` — every route declares its full error surface.
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

- `src/<project>/presentation/http/` — FastAPI routes and Pydantic schemas.
  Routes convert schemas to command/query DTOs and delegate to handlers.
  Error-to-HTTP mapping is per-route via `error_map={...}` (see below) — there
  is no global exception handler file.
  - `common/router.py` — `DishkaErrorAwareRoute` route class combining
    `ErrorAwareRoute` (from `fastapi-error-map`) with dishka auto-inject. Every
    `ErrorAwareRouter(...)` in routes passes `route_class=DishkaErrorAwareRoute`
    so handlers get `FromDishka[...]` resolved without manual `@inject`.
  - `common/errors/translators.py` — `NamedErrorTranslator` (strips `Error`
    suffix, emits `{"error": "<ClassName>"}`), `FieldErrorTranslator` (includes
    VO public attrs like `field`/`limit`/`reason`), `EntityNotFoundTranslator`
    (includes `entity_id`). Add a new translator here if a new error family
    needs a different response shape.
  - `common/errors/rules.py` — pre-composed `Rule` constants (`FIELD_ERROR_RULE`,
    `INVALID_TOKEN_RULE`, etc.) bundling status code + translator. Routes
    reference these constants in their `error_map` to stay consistent.
  - `common/schemas.py` — cross-route schemas (`FileSchema` etc.) shared
    between multiple routers.

- `src/<project>/bootstrap.py` — wiring functions: `setup_configs`,
  `setup_routes`, `setup_middlewares`, `setup_map_tables`,
  `setup_observability`. No `setup_exc_handlers` — error mapping lives on
  individual routes.

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

11. **`openapi.json` is the public frontend contract.** The generated schema
    must be sufficient on its own for an unfamiliar developer to build a
    fully working SPA (or a typed SDK via `openapi-generator` /
    `openapi-typescript`) without reading any backend source. The contract
    has two halves — operation-level metadata on every route (the checklist
    below) and `info.description`, the SPA's **operating manual** for
    everything cross-cutting that does not fit on a single operation.

    **Required `## ...` sections in `API_DESCRIPTION`** (`web.py`):

    - `## Authentication` — cookie names (`accessCookie`,
      `refreshCookie`, `signupSessionCookie`), their paths and
      lifetimes, and the rotation flow (when to call
      `POST /auth/refresh`, what `signupSessionCookie` is for).
    - `## Error responses` — every error envelope shape the API can
      produce (`FieldError`, `EntityNotFound`, named-error 401/403/409,
      Pydantic 422) and how the SPA should branch on them.
    - `## WebSocket channels` — see core rule 13. Every WS endpoint
      has its full protocol (auth, close codes, lifecycle, message
      shapes, `kind` enum) documented there because OpenAPI 3 does
      not model WebSockets natively.

    **Add a new `## ...` section whenever a new cross-cutting concept
    lands** — anything an SPA developer would otherwise have to infer
    by reading multiple route examples. Likely candidates as the API
    grows:

    - Pagination — the project's offset/limit convention lives in
      `application/common/pagination.py` (`DEFAULT_LIMIT = 20`,
      `MAX_LIMIT = 100`). The first list endpoint that ships with a
      paginated response is the trigger for a `## Pagination` section.
    - File uploads — the multipart flow in
      `presentation/http/common/uploads.py` plus the per-call-site
      caps in `presentation/http/common/upload_limits.py`. The
      `read_upload(file, *, max_bytes=...)` helper has no global
      default — every route picks an explicit constant
      (`USER_AVATAR_MAX_BYTES`, `LESSON_VIDEO_BLOCK_MAX_BYTES`, …)
      so "how big can this particular upload be" is visible at the
      call site. A `## File uploads` section should land alongside
      the first route that accepts user uploads.
    - Datetime serialization — ISO 8601 with timezone, server emits
      UTC. Document explicitly so SPAs do not parse naive strings.
    - Money / decimals, idempotency keys, rate limits, file formats,
      and any other concept the SPA must respect end-to-end.

    The bar: an unfamiliar SPA developer reading only `openapi.json`
    should be able to ship a working client — including WS channels —
    without asking the backend team a single question. If the SPA
    would need to ask, the answer belongs in `info.description`.

    Concretely, every new or modified route MUST satisfy:
    - **Operation metadata.** Pass `summary="..."` (short, becomes the
      OpenAPI `summary`) and a stable `operation_id="camelCaseVerb"`
      (becomes the SDK method name) on every `@router.<verb>(...)`. Never
      rely on FastAPI's auto-derived `register_auth_register_post`-style
      ids — they break SDK regeneration the moment a route is renamed.
    - **Tags.** Every router carries `tags=["<Aggregate>"]`. The
      human-readable description for the tag lives in `OPENAPI_TAGS` in
      `web.py`; add a new entry there when you introduce a new aggregate
      router.
    - **Request schemas.** Every Pydantic body model lives next to the
      route (or in `presentation/http/common/schemas.py` if shared) and
      every field uses `Field(description=..., examples=[...], ...)` with
      length / range constraints sourced from the aggregate's
      `entities/<aggregate>/constants.py` (see rule 12). Add a
      `model_config = ConfigDict(json_schema_extra={"examples": [...]})`
      with at least one full-body example.
    - **Response schemas.** Always declare `response_model=` (or a typed
      return annotation FastAPI can introspect). For routes with multiple
      success codes (e.g. 200 + 302), document the alternates via
      `responses={...}` including a `description` and, where relevant, a
      `headers={"Location": {...}}` block so codegen can produce the
      typed redirect path.
    - **Error responses.** Every exception the handler (or anything it
      awaits) can raise appears in `error_map={...}`. `fastapi-error-map`
      auto-populates the OpenAPI `responses` table with the matching
      response model — that's how 401/404/409/422 surface in
      `openapi.json`. Don't reach for `responses={...}` to add error
      codes manually; fix the `error_map` instead.
    - **Authentication.** Protected routes pass
      `dependencies=[Depends(access_cookie_scheme)]` (and/or the refresh
      / signup-session schemes from `auth_deps.py`). The `APIKeyCookie`
      dependency is a no-op at runtime (`auto_error=False`); its sole job
      is to register the cookie in OpenAPI's `securitySchemes` and tag
      the operation with the right `security:` requirement so generated
      clients know which cookie to send.
    - **Docstring.** Same Google-style rules as before (summary, `Args:`,
      `Returns:`, `Raises:`); the docstring becomes the operation
      `description` and is the long-form companion to `summary`.

    If `openapi.json` lacks any of the above, the contract is incomplete —
    fix the route, not the SPA.

12. **Schema length/range limits come from `entities/<aggregate>/constants.py`.**
    Every Pydantic request schema field that maps to a value object whose
    invariant references a `Final` constant (e.g. `FIRST_NAME_MAX_LEN`,
    `PASSWORD_MIN_LEN`, `DESCRIPTION_MAX_LEN`) MUST import that constant
    and pass it to `Field(min_length=..., max_length=..., ge=..., le=...)`.
    Mention the constant by name in the field's `description` so the
    OpenAPI doc tells the frontend dev where the limit comes from. The
    schema constraints are not a substitute for VO validation — the VO is
    still the source of truth and re-validates server-side — but they
    let the frontend reject bad input before a network round-trip and let
    `openapi-generator` produce client-side validators automatically.
    Inlining magic numbers in schemas (or duplicating limit values across
    `constants.py`, the VO, and the schema) is forbidden.

13. **WebSocket channels are part of the SPA contract too.** OpenAPI 3
    has no native model for WebSockets, but the SPA still needs the
    same kind of contract for them — paths, auth, message shapes,
    close codes, lifecycle. The single source of truth is the
    `## WebSocket channels` section inside `API_DESCRIPTION` in
    `web.py`. Every WS endpoint added under
    `presentation/http/routes/` MUST have a sub-section there.
    Concretely, each entry documents:

    - **Path** in the form `WS /path/{params}`.
    - **Direction** — read-only push (server → client), client-only
      send, or bidirectional.
    - **Authentication** — cookie scheme used (`accessCookie`, etc.).
      The same names registered under `securitySchemes` apply on the
      WS handshake; browsers send the cookie automatically.
    - **Close codes** — every WS-layer code the server may emit
      (`4401` for missing/denied auth, `4403` for authorisation
      failure, `4404` for missing or wrong-type resource, plus any
      channel-specific codes), each paired with the condition that
      triggers it.
    - **Lifecycle and replay policy** — when the connection closes
      naturally, whether events are buffered while the client is
      offline, what the client does on reconnect. The project's
      default is **no replay** — the client refetches initial state
      via REST and re-subscribes; explicitly call this out so the
      SPA does not assume otherwise.
    - **Bootstrap** — the REST endpoint(s) the client must fetch
      first to load initial state before opening the socket
      (e.g. `GET /products/{id}/content/draft` for the
      note-content channel).
    - **Server → client envelope** as a concrete JSON example.
    - **Client → server messages** (JSON shapes) if the channel is
      bidirectional. If the server currently ignores client
      messages, say so explicitly — silence is read as "may break in
      future" by SPA teams.
    - **`kind` value list** drawn directly from the relevant
      `<Aggregate>EventKind` enum in
      `application/common/.../events.py`. The enum is the source of
      truth — adding a new variant means updating the enum **and**
      this OpenAPI section in the same change.
    - **Payload semantics** — which `kind` values carry enough state
      to be applied directly versus which require a REST refetch.
      The SPA cannot guess this from the envelope alone.

    Tag descriptions of any aggregate that owns a WS channel
    (`Products`, `NoteContent`, `Presence`, etc.) MUST point at
    `## WebSocket channels` so a reader browsing Swagger UI by tag
    discovers the channel rather than missing it. The route module's
    docstring should be a brief pointer to the same section, never a
    duplicate of the protocol — duplicates drift.

    If the team later commits to typed payloads per `kind`, this rule
    still applies; a sibling `asyncapi.yaml` would supplement (not
    replace) the prose, the same way `openapi.json` supplements the
    `info.description` intro for HTTP.

14. **REST URL hierarchy: sub-resources live under their parent.** A
    resource that only exists in the context of an aggregate root is a
    sub-resource and its URL path must reflect that. Compound top-level
    paths like `/webinar-sessions`, `/webinar-schedules`,
    `/webinar-enrollments`, `/note-enrollments`, `/product-qa` are
    forbidden — they advertise a flat collection that does not exist
    in the domain (you cannot have a session without a cohort, an
    enrollment without a parent, a Q&A entry without a product). The
    correct shape is:

    ```
    /cohorts/{cohort_id}/sessions/{session_id}/...
    /cohorts/{cohort_id}/schedules/{schedule_id}
    /cohorts/{cohort_id}/enrollments/{enrollment_id}/...
    /notes/{note_id}/enrollments/{enrollment_id}/...
    /products/{product_id}/qa/{qa_id}/...
    ```

    Concrete consequences:

    - **Routers carry the parent path-parameter in their `prefix`.**
      `prefix="/cohorts/{cohort_id}/sessions"` (not `/webinar-sessions`).
      Every handler in such a router accepts the parent id as a path
      parameter (`cohort_id: UUID = _COHORT_ID_PATH`) — even when the
      command/query handler does not use it. The id is part of the
      URL contract; FastAPI parses and validates it, the SPA passes
      it, generated SDKs type-check it. Suffix unused parent params
      with `# noqa: ARG001` so ruff does not flag them.
    - **Collection-level operations (create, list) under the parent
      can live in the parent's route module** (e.g.
      `POST /cohorts/{cohort_id}/enrollments` lives in `cohort.py`),
      while item-level operations (single-item GET, PATCH, POST
      sub-actions) live in the child's own route module with the
      nested prefix. Both routers register independently with
      `app.include_router(...)` — FastAPI routes by full path so
      same-prefix routers do not conflict.
    - **The parent id is for URL framing, not enforcement.** The
      handler still authorises on the child id alone (e.g. session
      authorisation walks `session → cohort → product`). Validating
      that "session X actually belongs to cohort Y in the URL" is an
      extra DB round-trip with no security benefit — the global UUID
      already uniquely identifies the resource. If a SPA passes a
      mismatched parent id, the operation succeeds against the right
      child; this is the same pragmatic stance as Stripe / global-UUID
      REST APIs.
    - **Caller-scoped views (`/X/mine`) belong under
      `/users/me/...`.** A "list my enrollments across all cohorts"
      query is conceptually a property of the current user, not of
      a specific parent — so it lives at `/users/me/webinar-enrollments`
      and `/users/me/note-enrollments`, alongside the existing
      `/users/me/avatar`, `/users/me/first-name`, etc. Implement these
      as a sibling `me_router = ErrorAwareRouter(prefix="/users/me/...")`
      in the same file as the parent-nested router; export both, and
      register both in `bootstrap.setup_routes`. Never expose a flat
      `/<aggregate>/mine` endpoint. The `/users/me/...` URL space is
      the single namespace for "everything about the authenticated
      user."
    - **Caveat — globally-discoverable invitations.** A small handful
      of operations work on a child by global id without parent
      context because the actor does not yet have access to the
      parent (e.g. a `POST /collaborations/{id}/accept` invite the
      recipient is accepting; they do not necessarily know the
      product id yet). Treat these as the documented exception, not
      the rule, and limit them to invite/accept-style flows. Every
      other authenticated operation must nest.

    The shape of the URL tree must mirror the shape of the aggregate
    tree — if the SPA looks at `openapi.json` and cannot tell from
    the URLs which resource is a child of which, the URLs are wrong.

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
  - One-line imperative description (the route decorator's `summary=...`
    is the short OpenAPI `summary`; this docstring summary is the long
    `description` line).
  - `Args:` — every path/query/body/dependency parameter, what it means.
    Skip `interactor: FromDishka[...]` since it is not a public input.
  - `Returns:` — the response shape AND the relevant status codes / set
    cookies / `Location` headers. A frontend developer reading
    `openapi.json` should know whether to expect a body, a redirect, or
    just a status code.
  - `Raises:` — every domain/application error the handler can propagate
    (e.g. `EntityNotFoundError`, `FieldError` subclasses), plus the HTTP
    status the exception handler maps it to.
  Docstrings on application handlers, gateways, readers, and entities are
  encouraged but optional. Docstrings on routes are non-negotiable.
- **Every Pydantic schema at the HTTP boundary MUST carry OpenAPI
  metadata.** Each field uses `Field(description=..., examples=[...])`
  with constraints (`min_length`, `max_length`, `ge`, `le`) sourced from
  `entities/<aggregate>/constants.py` (see core rule 12). Each model
  attaches at least one full-body example via
  `model_config = ConfigDict(json_schema_extra={"examples": [...]})`.
  The model's class docstring describes what the schema represents and
  which route(s) consume it. This applies equally to request bodies,
  response bodies, and error response models — anything that ends up in
  `openapi.json`.

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
from dishka.integrations.fastapi import FromDishka
from fastapi import Depends, status
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from <project>.application.common.errors import EntityNotFoundError
from <project>.entities.<aggregate>.constants import <FIELD>_MAX_LEN
from <project>.entities.common.errors import FieldError
from <project>.presentation.http.common.auth_deps import access_cookie_scheme
from <project>.presentation.http.common.errors.rules import (
    AUTHENTICATED_WITH_FIELD_MAP,
    ENTITY_NOT_FOUND_RULE,
    FIELD_ERROR_RULE,
)
from <project>.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/<aggregate>s",
    tags=["<Aggregate>"],
    route_class=DishkaErrorAwareRoute,  # auto @inject + error_map support
)


class Add<Aggregate>Schema(BaseModel):
    """Body for `POST /<aggregate>s`."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"<field>": "<example>"}]},
    )

    <field>: str = Field(
        description=(
            "Human-readable description of <field>. "
            f"Max length is {<FIELD>_MAX_LEN} characters "
            "(`<FIELD>_MAX_LEN`)."
        ),
        min_length=1,
        max_length=<FIELD>_MAX_LEN,
        examples=["<example>"],
    )


@router.post(
    "/",
    summary="Create a new <aggregate>",
    operation_id="add<Aggregate>",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(access_cookie_scheme)],  # required when protected
    error_map=AUTHENTICATED_WITH_FIELD_MAP | {
        # add aggregate-specific errors here
    },
)
async def add(
    payload: Add<Aggregate>Schema,
    interactor: FromDishka[<Action><Aggregate>CommandHandler],
) -> <ReturnType>:
    """Create a new <aggregate>.

    Args:
        payload: Payload describing the <aggregate> to create
            (validated by Pydantic at the HTTP boundary; length
            limits come from `entities/<aggregate>/constants.py`).

    Returns:
        ``201 Created`` with `<ReturnType>` describing the new
        <aggregate>.

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401.
        EntityNotFoundError: A referenced related entity does not
            exist; HTTP 404 via `ENTITY_NOT_FOUND_RULE`.
        FieldError: One of the value-object invariants was violated;
            HTTP 422 via `FIELD_ERROR_RULE`.
    """
    return await interactor.run(<Action><Aggregate>Command(**payload.model_dump()))
```

**Why each piece is non-optional:**
- `summary` + `operation_id` → readable Swagger and clean SDK method
  names from `openapi-generator` / `openapi-typescript`.
- `dependencies=[Depends(access_cookie_scheme)]` → registers the
  `accessCookie` security scheme on the operation in `openapi.json`
  without changing runtime behavior (the scheme is `auto_error=False`;
  `Authenticator` still does the actual validation).
- `Field(description=, examples=, min_length=, max_length=)` with
  constants from `entities/<aggregate>/constants.py` → frontend gets
  validators for free; constants stay the single source of truth for
  domain limits (rule 12).
- Body example via `model_config = ConfigDict(json_schema_extra=...)`
  → Swagger "Try it out" works with one click; SDK fixtures can copy
  the example verbatim.

**Rules for `error_map`:**
- Every exception the handler (or anything it awaits — including shared helpers
  like `authenticate(...)`) can raise **must** appear in `error_map`. Unmapped
  exceptions become `RuntimeError("No rule defined for ...")` at request time —
  the loud failure is intentional, fix the map.
- Prefer the shared constants in `rules.py` over ad-hoc `rule(status=..., translator=...)`
  so the same error has the same response shape across routes.
- If a route needs an exception mapped **differently** from other routes, inline
  `rule(...)` with a custom status or translator. That's the whole point of
  per-route maps — don't try to work around the shared constants.
- `InvalidTokenError`, `EntityNotFoundError`, `InvalidCredentialsError`,
  `EmailAlreadyRegisteredError`, `EmailNotVerifiedError`, `FieldError` already
  have constants. Add new constants only when a new error appears in multiple
  routes.

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

### Error → HTTP mapping (per-route)

There is **no global exception handler file**. Each route declares its full
error surface in `error_map={...}` on its decorator, and the
`fastapi-error-map` runtime catches exceptions from the handler chain and
translates them through the rule's `translator` to a JSON response.

Pre-composed rules live in
`presentation/http/common/errors/rules.py`:

| Rule | Status | Translator output |
|---|---|---|
| `FIELD_ERROR_RULE` | 422 | `{"error": "<ClassName>", ...public VO attrs}` |
| `ENTITY_NOT_FOUND_RULE` | 404 | `{"error": "EntityNotFound", "entity_id": "..."}` |
| `INVALID_CREDENTIALS_RULE` | 401 | `{"error": "InvalidCredentials"}` |
| `INVALID_TOKEN_RULE` | 401 | `{"error": "InvalidToken"}` |
| `EMAIL_ALREADY_REGISTERED_RULE` | 409 | `{"error": "EmailAlreadyRegistered"}` |
| `EMAIL_NOT_VERIFIED_RULE` | 403 | `{"error": "EmailNotVerified"}` |

**Do not raise `HTTPException` from handlers** — raise domain/application
errors instead, let the route's `error_map` translate them.

**Exceptions not listed** in a route's `error_map` bubble up as
`RuntimeError("No rule defined for X")` (because `warn_on_unmapped=True` is
the library default), which Starlette turns into a 500. This is a **deliberate
loud failure** — fix the `error_map` instead of silencing it.

## Adding a new use case (checklist)

1. Create the DTO and handler in `application/{commands,queries}/<aggregate>/<n>.py`.
2. Implement the handler class with `@final`, `.run(data)`, deps via `__init__`.
3. If new persistence methods are needed:
   - extend the relevant `Protocol` in `application/common/persistence/<aggregate>.py`
   - implement in `infrastructure/persistence/adapters/<aggregate>.py` with `@override`
4. **Register the handler** in `ioc.interactors_provider` — add it to `provide_all(...)`.
5. Expose via a route in `presentation/http/routes/<aggregate>.py`, using
   a Pydantic schema for input validation if needed. Use `FromDishka[Handler]`.
   The router must be `ErrorAwareRouter(route_class=DishkaErrorAwareRoute)`;
   the decorator must carry an `error_map={...}` covering every exception
   the handler (and anything it awaits) can raise.
   **OpenAPI completeness checklist (core rule 11):**
   - `summary="..."` and a stable `operation_id="camelCaseVerb"` on the
     decorator.
   - `dependencies=[Depends(access_cookie_scheme)]` (and/or refresh /
     signup-session schemes) on every protected route.
   - `response_model=...` (or a typed return annotation) and any
     non-default success codes documented in `responses={...}`.
   - The request schema fields use `Field(description=, examples=, ...)`
     with length/range limits imported from
     `entities/<aggregate>/constants.py` (core rule 12).
   - The schema class has a docstring naming the route(s) it serves and
     a full body example via
     `model_config = ConfigDict(json_schema_extra={"examples": [...]})`.
   - The route docstring covers `Args:` / `Returns:` / `Raises:` per the
     code-style rule above.
6. If the handler introduces a **new** domain error:
   - Decide if it fits an existing rule (e.g. any new `FieldError` subclass
     is automatically covered by `FIELD_ERROR_RULE` via MRO matching — no
     new rule needed).
   - If not, add a `Rule` constant to
     `presentation/http/common/errors/rules.py`, reusing an existing
     translator if the response shape matches, or adding a new translator
     to `translators.py` if a bespoke shape is required.
   - Reference the new rule in the route's `error_map`.
7. Unit test in `tests/unit/application/...` using Mock-based fixtures
   (see `tests/unit/application/conftest.py` for the pattern).
8. Integration test in `tests/integrations/http/...` if the route is new.
9. If the use case introduces a **new WebSocket channel** (rare — most
   use cases are HTTP):
   - Place the route in `presentation/http/routes/<aggregate>_ws.py`
     using a plain `APIRouter`. `@router.websocket(...)` is not
     compatible with `ErrorAwareRouter`'s rule machinery — close the
     socket with the appropriate `4xxx` code on auth/authz failure
     instead of raising domain errors.
   - For event-driven channels, define `<Aggregate>EventKind` (StrEnum)
     and `<Aggregate>Event` (frozen slotted dataclass) in
     `application/common/<topic>/events.py`, plus an
     `<Aggregate>EventBus` Protocol next to it. Producers publish
     **after** the request transaction commits — never inside the
     transaction — so subscribers do not observe rolled-back mutations.
   - Add the channel's full protocol entry to `## WebSocket channels`
     in `API_DESCRIPTION` per core rule 13: path, direction, auth,
     close codes, lifecycle, bootstrap REST, envelope, client→server
     messages (or "not interpreted yet"), and the full list of `kind`
     values mirrored from the new enum.
   - Update the owning aggregate's tag description in `OPENAPI_TAGS`
     to point at `## WebSocket channels`.
10. **Verify the OpenAPI contract.** After wiring the route, regenerate
    `openapi.json` (e.g. `poetry run python -c "import json; from
    learnic.web import create_app_production; print(json.dumps(
    create_app_production().openapi()))"`) and confirm the new operation
    has: `summary`, `operationId`, request/response schemas with field
    `description` + `examples`, `security` (if protected), and an entry
    under `responses` for every error in `error_map`. For WS additions,
    grep `info.description` for the new channel path and every new
    `kind` value to confirm the prose contract is in sync. If any of
    the above is missing, the contract is incomplete — fix the route
    (or `API_DESCRIPTION`), not the SPA.

## Adding a new aggregate (checklist)

Beyond the use-case checklist, also:

1. `entities/<aggregate>/` with `models.py`, `value_objects.py`, `errors.py`, `__init__.py`.
2. `entities/<aggregate>/constants.py` for every length/range limit
   referenced by the aggregate's value-object invariants. These same
   constants are imported by request schemas (core rule 12), so add them
   here even if the first VO only uses one.
3. `application/common/persistence/<aggregate>.py` with `Gateway` and `Reader` protocols
   and any view models / filters specific to the aggregate.
4. `infrastructure/persistence/models/<aggregate>.py` with `sa.Table` + `map_<aggregate>_table()`.
5. Call the new `map_<aggregate>_table()` inside `bootstrap.setup_map_tables()`.
6. `infrastructure/persistence/adapters/<aggregate>.py` with `*MapperAlchemy` + `*ReaderAlchemy`.
7. Register mapper + reader in `ioc.gateways_provider` with explicit `provides=...`.
8. Alembic: `poetry run alembic revision --autogenerate -m "add <aggregate>"`,
   then `poetry run alembic upgrade head`.
9. **Add a tag entry in `OPENAPI_TAGS`** in `web.py` so the new aggregate's
   router shows up under a human-readable section in `openapi.json` and
   Swagger.

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
just dev            # bring up dev infra, apply migrations, run uvicorn + taskiq worker with reload
just prod           # docker compose up for the full production-like stack
just check          # ruff check + ruff format + codespell + mypy + bandit + semgrep
just dev-infra-up   # bring up Postgres, MinIO, Redis via docker-compose.dev (low-level)
just dev-infra-down # tear down dev containers (low-level)
```

`just dev` is the single daily-use recipe: it boots the dev dependencies,
applies migrations, and runs API + worker together with `--reload` on both.
`just check` bundles every static quality gate (linting, formatting,
typechecking, security scanners) into one command so CI and local runs
never diverge. Keep heavy/rare operations (tests, coverage) as ad-hoc
`poetry run ...` calls until the test suite grows enough to justify a
dedicated recipe again.

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
- ❌ Raise `HTTPException` from handlers or routes. Raise domain/application
  errors and list them in the route's `error_map={...}`; the
  `fastapi-error-map` runtime translates them into the configured JSON.
- ❌ Reintroduce a global exception-handler file or
  `app.add_exception_handler(...)`. Error-to-HTTP mapping is strictly
  per-route via `error_map`.
- ❌ Use bare `APIRouter(route_class=DishkaRoute)`. New routers are
  `ErrorAwareRouter(route_class=DishkaErrorAwareRoute)` so that both
  `FromDishka[...]` injection and `error_map` work.
- ❌ Silently swallow an unmapped exception by setting
  `warn_on_unmapped=False` — the noisy `RuntimeError("No rule defined for
  ...")` is a feature; fix the `error_map` of the offending route.
- ❌ Patch one missing entry in an `error_map` from a stack trace without
  auditing the sibling errors. When a handler can raise one of a family
  of related errors (state-mismatch families like
  `CannotAcceptInThisStatusError` / `CannotDeclineInThisStatusError` /
  `CannotRevokeInThisStatusError` / `CannotMutateInactiveCollaborationError`,
  invite-token failures, status-transition guards, …), they are reachable
  from real flows — map them in the **same** change. Otherwise you trade
  one 500 for another the next time the user trips a sibling status. The
  pattern is the same as on the frontend: when a bug is reported against
  one variant of a closed set (an enum, an error family, an event kind),
  audit every variant before declaring the fix done — the user reported
  one because that's the one they hit, the others are latent reports
  that haven't fired yet.
- ❌ Drop a domain-status check (`if self.status in (...): raise X`) on a
  state-machine entity without enumerating every status the operation is
  invalid in. The set of forbidden states is a closed set on
  `<Aggregate>Status` — list every variant explicitly, don't write
  `if self.status != ALLOWED: raise` and rely on a single allow-listed
  state. When a new status is added to the enum, every existing
  guard-clause must be revisited.
- ❌ Write an "is in use" / "is referenced" / "has dependents" gating
  query that filters only on the FK and ignores the lifecycle status
  of the related aggregate. Child / link / grant tables hold rows
  from **every** status the parent has ever been in — `PENDING_INVITE`,
  `ACTIVE`, `DECLINED`, `REVOKED`, archived, soft-deleted. A bare
  `WHERE fk_id = :id` treats dead audit-trail rows as live references.
  Same closed-set discipline as the guard-clause rule above: walk every
  value of `<Aggregate>Status` and pick a side for it explicitly
  (`WHERE status IN (PENDING_INVITE, ACTIVE)` for "still owes
  something," not "ever existed"). When a bug is reported against one
  variant of a closed set (an enum, an error family, a status), audit
  every variant before declaring the fix done — the reported one is
  the variant that fired, the others are latent and will fire next.
  Concrete past trap: a collaborator who declined or had their invite
  revoked kept the role-deletion check returning `True` forever
  because the dead grant row still pointed at the role.
- ❌ Ship an "in use" / "is referenced" semantic that the FK constraint
  disagrees with. If the gating query says "no live references" but
  the FK on those rows is `ON DELETE RESTRICT`, the handler will
  cheerfully proceed and Postgres will throw `IntegrityError` → 500.
  The application-level liveness check and the DB-level constraint
  must agree on what "free to delete" means. Pick one: purge the
  dead-state child rows alongside the parent in the same gateway
  operation (most common), declare the FK `ON DELETE SET NULL` /
  `CASCADE` if the child should follow the parent, or count the
  audit-trail rows as live in the check (and refuse deletion).
  Whenever you change a status-aware gating query, re-read the FK
  on the same table — they are two halves of one invariant.
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
  `__post_init__`, entity methods, **or Pydantic schemas**. They live in
  the aggregate's `constants.py` as `Final` values and are imported by
  the VOs, by any adapter that needs the same limit (e.g.
  `sa.String(FIRST_NAME_MAX_LEN)`), and by every Pydantic request/response
  schema field that mirrors the same invariant (e.g.
  `Field(max_length=FIRST_NAME_MAX_LEN)` — see core rule 12).
- ❌ Define a route without `summary=` and `operation_id=` on the
  decorator. Auto-derived `register_auth_register_post`-style ids break
  client SDK regeneration the moment the route is renamed (rule 11).
- ❌ Use `tags=[...]` on a router without adding a matching entry in
  `OPENAPI_TAGS` in `web.py`. Untagged or undocumented tags produce a
  Swagger UI without aggregate descriptions.
- ❌ Define a Pydantic schema field as a bare type (`email: str`,
  `value: str | None`) at the HTTP boundary. Every field needs
  `Field(description=, examples=[...], min_length=/max_length=/...)`
  using constants from `entities/<aggregate>/constants.py` so OpenAPI
  carries the same constraints the domain enforces.
- ❌ Hand-roll `responses={401: {...}, 422: {...}}` on a route to
  document errors. `fastapi-error-map` does that automatically from
  `error_map={...}`. If a status is missing from `openapi.json`, the
  fix is in `error_map` — not in `responses`.
- ❌ Use a route's `responses={...}` to document error shapes that should
  belong to a `Rule` constant. Routes share rules through
  `presentation/http/common/errors/rules.py`; ad-hoc `responses` entries
  drift over time.
- ❌ Mark a route protected without
  `dependencies=[Depends(access_cookie_scheme)]` (or the relevant cookie
  scheme). The `Authenticator` will still raise `InvalidTokenError` at
  runtime, but `openapi.json` won't list the cookie under
  `securitySchemes` and generated SDKs won't know to send it.
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
- ❌ Add a WebSocket endpoint without a corresponding sub-section in
  `## WebSocket channels` in `API_DESCRIPTION`. Module docstrings, PR
  descriptions, and chat threads do not count — the SPA contract lives
  in `openapi.json` and that is the only file the frontend is
  guaranteed to read (rule 13).
- ❌ Document a WebSocket protocol exclusively in the route's module
  docstring. The docstring is a brief pointer; the contract — auth,
  close codes, envelope, `kind` values, payload semantics — lives in
  `API_DESCRIPTION` so it surfaces in `openapi.json` (rule 13).
  Duplicating the protocol in both places guarantees drift.
- ❌ Inline `kind` value lists in WS protocol docs that drift from the
  `<Aggregate>EventKind` enum. The enum is the source of truth —
  adding, renaming, or removing a variant means updating the enum
  **and** the `## WebSocket channels` list in the same change
  (rule 13).
- ❌ Introduce a new cross-cutting SPA concern (a new pagination
  convention, an upload flow, a datetime-format rule, a money format,
  idempotency keys, rate limits) without adding a `## ...` section to
  `API_DESCRIPTION`. If the SPA needs to know it and it does not fit
  on a single operation, it belongs in the operating manual at the
  top of `info.description` (rule 11).
- ❌ Publish a domain event from inside a request transaction (i.e.
  before `await transaction.commit()` returns). Subscribers on a WS
  channel would observe deltas for mutations that get rolled back on
  a later failure. Publish strictly **after** commit so the channel
  only sees committed state (rule 13).
- ❌ Expose a sub-resource as a flat top-level collection
  (`/webinar-sessions`, `/webinar-schedules`, `/webinar-enrollments`,
  `/note-enrollments`, `/product-qa`, etc.). Sub-resources nest under
  their parent; the URL must mirror the aggregate tree. See rule 14
  for the exact shape and the narrow invitation-flow exception.
- ❌ Expose a `/<aggregate>/mine` (or `/<aggregate>/me`) endpoint at
  the top level. Caller-scoped views go under `/users/me/...` —
  define a sibling `me_router` in the same module and register it in
  `bootstrap.setup_routes` (rule 14). The `/users/me/...` URL space
  is the single namespace for "everything about the authenticated
  user" alongside `/users/me/avatar`, `/users/me/first-name`, etc.
- ❌ Drop the parent path-parameter from a nested router's prefix to
  "save typing." `prefix="/cohorts/{cohort_id}/sessions"` is the
  contract — the parent id appears in every operation under it, even
  if the application handler does not consume it. The id is part of
  the URL surface, not a runtime concern (rule 14).

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