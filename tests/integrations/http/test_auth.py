from http import HTTPStatus

from httpx import AsyncClient

"""Light integration tests that exercise routing + error mapping without DB.

The full flow (register -> verify -> login -> refresh -> logout) needs
a live Postgres and the new runtime deps (``argon2-cffi``, ``pyjwt``)
installed via ``poetry sync`` — tracked separately. These tests only
cover paths that short-circuit before touching the session.
"""


async def test_refresh_without_cookie_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post("/auth/refresh")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_verify_wait_without_cookie_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.get("/auth/email-verification/wait")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_me_without_cookie_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.get("/auth/me")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_logout_without_cookie_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post("/auth/logout")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_verify_email_missing_token_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post("/auth/email-verification/verify", json={})
    # Pydantic validation error at the HTTP boundary.
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
