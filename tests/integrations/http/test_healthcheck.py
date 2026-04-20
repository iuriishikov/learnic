from http import HTTPStatus

from httpx import AsyncClient


async def test_healthcheck_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthcheck")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}
