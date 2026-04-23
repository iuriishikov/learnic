from http import HTTPStatus

from httpx import AsyncClient

"""Route-level tests for user profile change endpoints.

Only the unauthenticated paths are covered here (they short-circuit
before hitting the DB). The full happy-path flow needs a live Postgres
and is tracked with other DB-backed integration tests.
"""


async def test_change_first_name_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.put("/users/me/first-name", json={"value": "New"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_change_last_name_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.put("/users/me/last-name", json={"value": "New"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_change_patronymic_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.put("/users/me/patronymic", json={"value": None})
    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_change_description_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.put("/users/me/description", json={"value": "<p>hi</p>"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED
