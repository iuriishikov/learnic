from http import HTTPStatus
from uuid import uuid4

from httpx import AsyncClient

"""Route-level tests for the admin subscription grant/revoke endpoints.

Only the unauthenticated paths are covered here — they short-circuit in
``AdminAuthenticator.authenticate_admin`` before any DB access, the same
scope as the other route tests in this suite. The admin (403), missing
user (404), unknown-plan / past-expiry (422), and happy-path (201/204)
flows all need a live Postgres and a seeded admin caller, and are tracked
with the other DB-backed integration tests.
"""


async def test_grant_subscription_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post(
        f"/admin/users/{uuid4()}/subscription",
        json={"plan_code": "BETA"},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_grant_subscription_empty_body_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    # Both fields default, so an empty body is valid input — the
    # request still reaches the handler and is rejected for auth.
    response = await client.post(
        f"/admin/users/{uuid4()}/subscription",
        json={},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_revoke_subscription_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.delete(f"/admin/users/{uuid4()}/subscription")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}
