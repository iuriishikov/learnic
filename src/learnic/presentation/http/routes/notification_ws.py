"""Per-user notification WebSocket channel.

One-way push of :class:`NotificationEvent` deltas to the panel —
``created`` (new card), ``updated`` (existing card patched),
``read`` (single card flipped), ``read_all`` (double-check).
Same shape and authentication as the existing collaboration
channel; the contract is documented in
``## WebSocket channels`` of the OpenAPI ``info.description``.

Per-kind serialization is dispatched through the
:class:`NotificationKindRegistry` — the WS layer never learns
about specific kinds, so adding a new one needs no change here.
"""

from typing import Any

from dishka import AsyncContainer
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.notifications.event_bus import (
    NotificationCreatedEvent,
    NotificationEvent,
    NotificationEventBus,
    NotificationEventKind,
    NotificationReadAllEvent,
    NotificationReadEvent,
    NotificationUpdatedEvent,
)
from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
)
from learnic.application.common.notifications.views import (
    NotificationDetailsView,
    NotificationView,
)
from learnic.infrastructure.notifications.specs._helpers import actor_to_ws
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/users/me")


def _details(
    view: NotificationDetailsView,
    registry: NotificationKindRegistry,
) -> dict[str, Any]:
    spec = registry.by_view(view)
    return {"type": spec.kind.value, **spec.to_ws_dict(view)}


def _notification(
    view: NotificationView,
    registry: NotificationKindRegistry,
) -> dict[str, Any]:
    return {
        "oid": str(view.oid),
        "kind": view.kind.value,
        "category": view.category.value,
        "actor": actor_to_ws(view.actor),
        "created_at": view.created_at.isoformat(),
        "read_at": view.read_at.isoformat() if view.read_at else None,
        "details": _details(view.details, registry),
    }


def _envelope(
    event: NotificationEvent,
    registry: NotificationKindRegistry,
) -> dict[str, Any]:
    if isinstance(event, NotificationCreatedEvent):
        return {
            "kind": NotificationEventKind.CREATED.value,
            "notification": (
                _notification(event.notification, registry)
                if event.notification is not None
                else None
            ),
        }
    if isinstance(event, NotificationUpdatedEvent):
        return {
            "kind": NotificationEventKind.UPDATED.value,
            "notification": _notification(event.notification, registry),
        }
    if isinstance(event, NotificationReadEvent):
        return {
            "kind": NotificationEventKind.READ.value,
            "notification_id": str(event.notification_id),
        }
    if isinstance(event, NotificationReadAllEvent):
        return {"kind": NotificationEventKind.READ_ALL.value}
    raise NotImplementedError(f"Unknown event: {event!r}")


@router.websocket("/notifications")
async def notifications_ws(websocket: WebSocket) -> None:
    """One-way push of notification deltas to the connecting user.

    The recipient is derived from the access cookie — there is no
    path parameter, so a user can subscribe to exactly their own
    channel and nothing else. Authentication failures close with
    ``4401`` before ``accept``.
    """
    container: AsyncContainer = websocket.app.state.dishka_container

    async with container() as request_scope:
        auth = await request_scope.get(Authenticator)
        try:
            ctx = await auth.authenticate_websocket(websocket)
        except InvalidTokenError:
            await websocket.close(code=4401, reason="invalid token")
            return

    event_bus = await container.get(NotificationEventBus)
    registry = await container.get(NotificationKindRegistry)

    await websocket.accept()
    try:
        async for event in event_bus.subscribe(ctx.user_id):
            await websocket.send_json(_envelope(event, registry))
    except WebSocketDisconnect:
        pass
