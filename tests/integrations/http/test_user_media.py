from http import HTTPStatus

from httpx import AsyncClient

"""Route-level tests that don't need a live Postgres.

The upload/delete paths short-circuit at the access-cookie check when
there is no valid cookie — these tests only verify that the routes are
registered and the auth dependency fires before any storage calls.
"""


async def test_upload_avatar_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/users/me/avatar",
        files={"file": ("x.jpg", b"binary", "image/jpeg")},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_delete_avatar_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.delete("/users/me/avatar")

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_upload_cover_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/users/me/cover",
        files={"file": ("x.jpg", b"binary", "image/jpeg")},
    )

    assert response.status_code == HTTPStatus.UNAUTHORIZED


async def test_delete_cover_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.delete("/users/me/cover")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
