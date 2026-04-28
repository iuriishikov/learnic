from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from learnic.bootstrap import (
    setup_configs,
    setup_map_tables,
    setup_routes,
)
from learnic.infrastructure.configs import Configs
from learnic.infrastructure.tasks.broker import broker
from learnic.ioc import setup_providers

API_TITLE: Final = "Learnic API"
API_VERSION: Final = "0.1.0"
API_DESCRIPTION: Final = """
HTTP API for the Learnic learning platform.

This document is the **single source of truth for the frontend**: every
request body, response body, status code, and error shape that the SPA
needs is described here. Anything not in this schema is not part of the
public contract.

## Authentication

The API authenticates browsers exclusively through HttpOnly cookies set
by the auth flow — there is no `Authorization` header path:

- `accessCookie` (`access_token`, path `/`) — sent on every protected
  request. Lifetime is short; rotate via `POST /auth/refresh` when a
  401 `InvalidToken` lands.
- `refreshCookie` (`refresh_token`, path `/auth/refresh`) — used only
  by `POST /auth/refresh` and `POST /auth/logout`.
- `signupSessionCookie` (`signup_session`, path `/auth`) — installed by
  `POST /auth/register` and polled by
  `GET /auth/email-verification/wait` to auto-login the registration
  tab once the user clicks the verification link.

Browsers handle these cookies automatically; SPAs only need
`fetch(..., { credentials: "include" })` (or the equivalent in their
HTTP client). Mobile / non-browser clients should persist the
`Set-Cookie` values and replay them.

## Error responses

Every error this API can produce is documented per-operation under the
appropriate status code and follows one of three shapes:

- **422 `FieldError`** — value-object invariant violated. Body is
  `{"error": "<ErrorClassName>", ...public_attrs}` where extras carry
  context (`field`, `limit`, `reason`, ...). Typed via
  `FieldErrorResponseModel`.
- **404 `EntityNotFound`** — body is
  `{"error": "EntityNotFound", "entity_id": "<uuid>"}`.
- **401 / 403 / 409 named errors** — body is
  `{"error": "<ClassNameWithoutErrorSuffix>"}` (e.g.
  `"InvalidCredentials"`, `"InvalidToken"`, `"EmailAlreadyRegistered"`,
  `"EmailNotVerified"`).

Validation failures from Pydantic (request body type/length) come back
as the standard FastAPI 422 envelope (`{"detail": [...]}`); domain VO
violations come back as the `FieldError` shape above. Both share the
same status code; clients should branch on the response body.
""".strip()

OPENAPI_TAGS: Final[list[dict[str, Any]]] = [
    {
        "name": "Root",
        "description": (
            "Liveness and welcome endpoints. Not protected and not "
            "intended for SPA consumption — present so deployment "
            "tooling (Docker, Caddy) has something to probe."
        ),
    },
    {
        "name": "Auth",
        "description": (
            "Registration, login, token rotation, logout, email "
            "verification, and password reset. All session state is "
            "kept in HttpOnly cookies; the SPA never touches a token "
            "directly."
        ),
    },
    {
        "name": "Users",
        "description": (
            "User profile reads and edits. `GET /users/{user_id}` is "
            "public; everything under `/users/me/...` requires the "
            "`accessCookie` security scheme."
        ),
    },
]


@asynccontextmanager
async def _lifespan(_: FastAPI) -> AsyncIterator[None]:
    await broker.startup()
    try:
        yield
    finally:
        await broker.shutdown()


def _create_app(configs: Configs) -> FastAPI:
    setup_map_tables()
    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=_lifespan,
    )
    setup_routes(app)
    container = setup_providers(configs)
    setup_dishka(container, app)
    return app


def create_app_production() -> FastAPI:
    return _create_app(setup_configs())


def create_app_tests(configs: Configs) -> FastAPI:
    return _create_app(configs)
