"""Route-level tests for presence endpoints.

Only the unauthenticated paths are covered here — the full WS lifecycle
needs a live Redis and is out of scope for the static-only test
profile. These tests verify routing, auth dependency wiring, and the
WebSocket handshake-time close behavior.
"""

import uuid
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.websockets import WebSocketDisconnect

from learnic.infrastructure.configs import Configs
from learnic.web import create_app_tests


async def test_get_presence_without_auth_returns_401(
    client: AsyncClient,
) -> None:
    response = await client.get(f"/presence/{uuid.uuid4()}")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json() == {"error": "InvalidToken"}


async def test_get_presence_with_malformed_uuid_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.get("/presence/not-a-uuid")

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_ws_without_cookie_closes_with_4401(configs: Configs) -> None:
    # WS test uses starlette's sync TestClient because httpx's
    # AsyncClient doesn't speak WebSocket. The handler closes the
    # socket *before* accept() when the access cookie is missing,
    # which surfaces as a WebSocketDisconnect at the client.
    app = create_app_tests(configs)
    with TestClient(app) as c, pytest.raises(WebSocketDisconnect) as exc:
        with c.websocket_connect("/presence/ws"):
            pass

    assert exc.value.code == 4401
