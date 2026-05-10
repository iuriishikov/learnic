"""Per-user notification WebSocket channel.

One-way push of :class:`NotificationEvent` deltas to the panel —
``created`` (new card), ``read`` (single card flipped), ``read_all``
(double-check). Same shape and authentication as the existing
collaboration channel; the contract is documented in
``## WebSocket channels`` of the OpenAPI ``info.description``.
"""

from typing import Any

from dishka import AsyncContainer
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.formatting import build_full_name, mask_email
from learnic.application.common.notifications.event_bus import (
    NotificationCreatedEvent,
    NotificationEvent,
    NotificationEventBus,
    NotificationEventKind,
    NotificationReadAllEvent,
    NotificationReadEvent,
    NotificationUpdatedEvent,
)
from learnic.application.common.notifications.views import (
    AccessRevokedView,
    CollaborationSnapshotView,
    InviteAcceptedView,
    InviteDeclinedView,
    InviteSentView,
    NotificationDetailsView,
    NotificationView,
    ProductRefView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.presentation.http.common.auth_deps import Authenticator

router = APIRouter(prefix="/users/me")


def _actor(actor: UserRefView | None) -> dict[str, Any] | None:
    if actor is None:
        return None
    return {
        "oid": str(actor.oid),
        "full_name": build_full_name(
            actor.first_name, actor.last_name, actor.patronymic
        ),
        "email": mask_email(actor.email) if actor.email else "",
    }


def _product(product: ProductRefView) -> dict[str, Any]:
    return {"oid": str(product.oid), "name": product.name}


def _collaboration(
    snapshot: CollaborationSnapshotView | None,
) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "status": snapshot.status.value,
        "accepted_at": (
            snapshot.accepted_at.isoformat()
            if snapshot.accepted_at is not None
            else None
        ),
        "declined_at": (
            snapshot.declined_at.isoformat()
            if snapshot.declined_at is not None
            else None
        ),
        "revoked_at": (
            snapshot.revoked_at.isoformat() if snapshot.revoked_at is not None else None
        ),
        "invite_expires_at": (
            snapshot.invite_expires_at.isoformat()
            if snapshot.invite_expires_at is not None
            else None
        ),
    }


def _details(view: NotificationDetailsView) -> dict[str, Any]:
    if isinstance(view, InviteSentView):
        return {
            "type": "invite_sent",
            "collaboration_id": str(view.collaboration_id),
            "product": _product(view.product),
            "collaboration": _collaboration(view.collaboration),
        }
    if isinstance(view, InviteAcceptedView):
        return {
            "type": "invite_accepted",
            "collaboration_id": str(view.collaboration_id),
            "product": _product(view.product),
            "collaborator": _actor(view.collaborator),
            "collaboration": _collaboration(view.collaboration),
            "viewer_can_manage_collaborators": (view.viewer_can_manage_collaborators),
        }
    if isinstance(view, InviteDeclinedView):
        return {
            "type": "invite_declined",
            "collaboration_id": str(view.collaboration_id),
            "product": _product(view.product),
            "decliner": _actor(view.decliner),
            "collaboration": _collaboration(view.collaboration),
            "viewer_can_manage_collaborators": (view.viewer_can_manage_collaborators),
        }
    if isinstance(view, AccessRevokedView):
        return {
            "type": "access_revoked",
            "collaboration_id": str(view.collaboration_id),
            "product": _product(view.product),
            "revoker": _actor(view.revoker),
        }
    raise NotImplementedError(
        f"Cannot serialize details: {type(view).__name__}",
    )


def _notification(view: NotificationView) -> dict[str, Any]:
    return {
        "oid": str(view.oid),
        "kind": view.kind.value,
        "category": view.category.value,
        "actor": _actor(view.actor),
        "created_at": view.created_at.isoformat(),
        "read_at": view.read_at.isoformat() if view.read_at else None,
        "details": _details(view.details),
    }


def _envelope(event: NotificationEvent) -> dict[str, Any]:
    if isinstance(event, NotificationCreatedEvent):
        return {
            "kind": NotificationEventKind.CREATED.value,
            "notification": (
                _notification(event.notification)
                if event.notification is not None
                else None
            ),
        }
    if isinstance(event, NotificationUpdatedEvent):
        return {
            "kind": NotificationEventKind.UPDATED.value,
            "notification": _notification(event.notification),
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

    await websocket.accept()
    try:
        async for event in event_bus.subscribe(ctx.user_id):
            await websocket.send_json(_envelope(event))
    except WebSocketDisconnect:
        pass
