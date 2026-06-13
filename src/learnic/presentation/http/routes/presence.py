"""Presence HTTP query + WebSocket push routes.

The HTTP endpoints answer one-off "is this user online?" questions and
appear in the OpenAPI schema. The WebSocket endpoint maintains a
long-lived push channel where the client subscribes to user ids of
interest and receives ``snapshot`` and ``presence`` deltas as their
status changes. The act of holding the WebSocket open is itself the
"I'm online" signal — no application-level message is required.
"""

import asyncio
import json
import uuid
from typing import Final
from uuid import UUID

from dishka import AsyncContainer
from dishka.integrations.fastapi import FromDishka
from fastapi import (
    Depends,
    Path,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi_error_map import ErrorAwareRouter
from pydantic import BaseModel, ConfigDict, Field

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.presence.event_bus import PresenceEventBus
from learnic.application.common.presence.tracker import PresenceTracker
from learnic.application.queries.presence.get_user_presence import (
    GetUserPresenceQuery,
    GetUserPresenceQueryHandler,
    UserPresenceView,
)
from learnic.entities.presence.constants import (
    HEARTBEAT_INTERVAL_SECONDS,
    MAX_PRESENCE_SUBSCRIPTIONS,
)
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.auth_deps import (
    Authenticator,
    access_cookie_scheme,
)
from learnic.presentation.http.common.errors.rules import INVALID_TOKEN_RULE
from learnic.presentation.http.common.router import DishkaErrorAwareRoute

router = ErrorAwareRouter(
    prefix="/presence",
    tags=["Presence"],
    route_class=DishkaErrorAwareRoute,
)

_AUTH_SECURITY: Final = [Depends(access_cookie_scheme)]

_USER_ID_PATH: Final = Path(
    description="Target user's UUID.",
    examples=["550e8400-e29b-41d4-a716-446655440000"],
)


class UserPresenceSchema(BaseModel):
    """Response of `GET /presence/{user_id}`.

    Carries a per-user snapshot — `status` is `online` if at least one
    of the user's sessions has refreshed its heartbeat within the
    server-side TTL, otherwise `offline`.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "online",
                },
            ],
        },
    )

    user_id: UUID = Field(
        description="User identifier whose presence is reported.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    status: PresenceStatus = Field(
        description=(
            "Current presence status. `online` means the user has at "
            "least one live session; `offline` means none."
        ),
        examples=["online"],
    )

    @classmethod
    def from_view(cls, view: UserPresenceView) -> "UserPresenceSchema":
        return cls(user_id=view.user_id, status=view.status)


@router.get(
    "/{user_id}",
    summary="Get a user's current presence",
    operation_id="getUserPresence",
    status_code=status.HTTP_200_OK,
    dependencies=_AUTH_SECURITY,
    response_model=UserPresenceSchema,
    error_map={InvalidTokenError: INVALID_TOKEN_RULE},
)
async def get_presence(
    request: Request,
    interactor: FromDishka[GetUserPresenceQueryHandler],
    auth: FromDishka[Authenticator],
    user_id: UUID = _USER_ID_PATH,
) -> UserPresenceSchema:
    """Return whether ``user_id`` currently has at least one live session.

    Use this for one-off lookups (e.g. opening a profile page). For
    real-time updates of multiple users, prefer the
    ``/presence/ws`` WebSocket — repeated polling is wasteful and
    laggy compared to the push channel.

    Args:
        request: Source of the access-token cookie.
        user_id: Target user's UUID, parsed from the URL path.
        interactor: Injected presence query handler.
        auth: Injected authenticator that validates the access cookie.

    Returns:
        ``200 OK`` with :class:`UserPresenceSchema` (`online` or
        `offline`).

    Raises:
        InvalidTokenError: Missing or denied access cookie; HTTP 401
            via ``INVALID_TOKEN_RULE``.
    """
    await auth.authenticate(request)
    view = await interactor.run(GetUserPresenceQuery(user_id=UserID(user_id)))
    return UserPresenceSchema.from_view(view)


# ────────────────────────── WebSocket ──────────────────────────


def _presence_payload(user_id: UserID, online: bool) -> dict[str, str]:
    return {
        "user_id": str(user_id),
        "status": (PresenceStatus.ONLINE if online else PresenceStatus.OFFLINE).value,
    }


def _parse_user_ids(raw: object) -> set[UserID]:
    if not isinstance(raw, list):
        return set()
    parsed: set[UserID] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        try:
            parsed.add(UserID(uuid.UUID(item)))
        except ValueError:
            continue
    return parsed


@router.websocket("/ws")
async def presence_ws(websocket: WebSocket) -> None:
    """Bidirectional presence stream.

    **Auth.** Reuses the standard ``accessCookie`` HttpOnly cookie —
    browsers send it on the WS handshake automatically. Failure
    closes the socket with code ``4401`` before ``accept`` is called.

    **Lifecycle.** Holding the socket open marks the connecting user
    online; closing it marks them offline (no application-level
    message required). The server refreshes the connection's freshness
    every ``HEARTBEAT_INTERVAL_SECONDS`` so the underlying TTL never
    expires while the WS is alive.

    **Protocol.** Messages are JSON. Client → server:

    - ``{"type": "subscribe",   "user_ids": ["<uuid>", ...]}``
    - ``{"type": "unsubscribe", "user_ids": ["<uuid>"]}``

    Server → client:

    - ``{"type": "snapshot", "presences": [{"user_id": ..., "status":
      "online" | "offline"}]}`` — sent immediately after each
      ``subscribe``, contains the current state of the just-added ids.
    - ``{"type": "presence", "user_id": ..., "status": ...}`` —
      delta pushed when one of the subscribed users changes status.

    Subscriptions are scoped to this connection only: reconnects
    must re-send the desired ``subscribe`` list.
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    # short-lived request scope so the DB session used by the
    # ``TokenDenylist`` check is released immediately after auth and
    # not held for the full WebSocket lifetime
    async with container() as request_scope:
        auth = await request_scope.get(Authenticator)
        try:
            ctx = await auth.authenticate_websocket(websocket)
        except InvalidTokenError:
            await websocket.close(code=4401, reason="invalid token")
            return

    tracker = await container.get(PresenceTracker)
    event_bus = await container.get(PresenceEventBus)

    await websocket.accept()
    conn_id = str(uuid.uuid4())
    subscriptions: set[UserID] = set()

    async def receive_loop() -> None:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(msg, dict):
                continue
            kind = msg.get("type")
            ids = _parse_user_ids(msg.get("user_ids"))
            if kind == "subscribe" and ids:
                # Bound the per-connection subscription set: drop ids
                # once the cap is reached so a client cannot grow memory
                # / the Redis pipeline without limit.
                capacity = MAX_PRESENCE_SUBSCRIPTIONS - len(subscriptions)
                if capacity <= 0:
                    continue
                accepted = list(ids)[:capacity]
                subscriptions.update(accepted)
                online = await tracker.filter_online(accepted)
                await websocket.send_json(
                    {
                        "type": "snapshot",
                        "presences": [
                            _presence_payload(uid, uid in online)
                            for uid in accepted
                        ],
                    },
                )
            elif kind == "unsubscribe" and ids:
                subscriptions.difference_update(ids)

    async def forward_loop() -> None:
        async for event in event_bus.subscribe():
            if event.user_id in subscriptions:
                await websocket.send_json(
                    {
                        "type": "presence",
                        "user_id": str(event.user_id),
                        "status": event.status.value,
                    },
                )

    async def heartbeat_loop() -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            await tracker.heartbeat(ctx.user_id, conn_id)

    await tracker.mark_online(ctx.user_id, conn_id)
    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(receive_loop())
            tg.create_task(forward_loop())
            tg.create_task(heartbeat_loop())
    except* WebSocketDisconnect:
        pass
    finally:
        await tracker.mark_offline(ctx.user_id, conn_id)
