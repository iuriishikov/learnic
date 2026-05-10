import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final

from redis.asyncio import Redis
from typing_extensions import override

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
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


def _channel(recipient_id: UserID) -> str:
    return f"notif:{recipient_id}"


def _serialize_actor(actor: UserRefView | None) -> dict[str, Any] | None:
    if actor is None:
        return None
    return {
        "oid": str(actor.oid),
        "email": actor.email,
        "first_name": actor.first_name,
        "last_name": actor.last_name,
        "patronymic": actor.patronymic,
    }


def _serialize_product(product: ProductRefView) -> dict[str, Any]:
    return {"oid": str(product.oid), "name": product.name}


def _serialize_collaboration(
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
            snapshot.revoked_at.isoformat()
            if snapshot.revoked_at is not None
            else None
        ),
        "invite_expires_at": (
            snapshot.invite_expires_at.isoformat()
            if snapshot.invite_expires_at is not None
            else None
        ),
    }


def _serialize_details(details: NotificationDetailsView) -> dict[str, Any]:
    if isinstance(details, InviteSentView):
        return {
            "type": "invite_sent",
            "collaboration_id": str(details.collaboration_id),
            "product": _serialize_product(details.product),
            "collaboration": _serialize_collaboration(details.collaboration),
        }
    if isinstance(details, InviteAcceptedView):
        return {
            "type": "invite_accepted",
            "collaboration_id": str(details.collaboration_id),
            "product": _serialize_product(details.product),
            "collaborator": _serialize_actor(details.collaborator),
            "collaboration": _serialize_collaboration(details.collaboration),
            "viewer_can_manage_collaborators": (
                details.viewer_can_manage_collaborators
            ),
        }
    if isinstance(details, InviteDeclinedView):
        return {
            "type": "invite_declined",
            "collaboration_id": str(details.collaboration_id),
            "product": _serialize_product(details.product),
            "decliner": _serialize_actor(details.decliner),
            "collaboration": _serialize_collaboration(details.collaboration),
            "viewer_can_manage_collaborators": (
                details.viewer_can_manage_collaborators
            ),
        }
    if isinstance(details, AccessRevokedView):
        return {
            "type": "access_revoked",
            "collaboration_id": str(details.collaboration_id),
            "product": _serialize_product(details.product),
            "revoker": _serialize_actor(details.revoker),
        }
    raise NotImplementedError(
        f"Cannot serialize notification details: {type(details).__name__}",
    )


def _serialize_notification(view: NotificationView) -> dict[str, Any]:
    return {
        "oid": str(view.oid),
        "recipient_id": str(view.recipient_id),
        "kind": view.kind.value,
        "category": view.category.value,
        "actor": _serialize_actor(view.actor),
        "created_at": view.created_at.isoformat(),
        "read_at": view.read_at.isoformat() if view.read_at else None,
        "details": _serialize_details(view.details),
    }


def _serialize(event: NotificationEvent) -> str:
    if isinstance(event, NotificationCreatedEvent):
        return json.dumps(
            {
                "kind": NotificationEventKind.CREATED.value,
                "notification": (
                    _serialize_notification(event.notification)
                    if event.notification is not None
                    else None
                ),
            },
        )
    if isinstance(event, NotificationUpdatedEvent):
        return json.dumps(
            {
                "kind": NotificationEventKind.UPDATED.value,
                "notification": _serialize_notification(event.notification),
            },
        )
    if isinstance(event, NotificationReadEvent):
        return json.dumps(
            {
                "kind": NotificationEventKind.READ.value,
                "notification_id": str(event.notification_id),
            },
        )
    if isinstance(event, NotificationReadAllEvent):
        return json.dumps({"kind": NotificationEventKind.READ_ALL.value})
    raise NotImplementedError(f"Unknown notification event: {event!r}")


def _deserialize_actor(data: dict[str, Any] | None) -> UserRefView | None:
    if data is None:
        return None
    return UserRefView(
        oid=UserID(uuid.UUID(data["oid"])),
        email=data.get("email", ""),
        first_name=data["first_name"],
        last_name=data["last_name"],
        patronymic=data.get("patronymic"),
    )


def _deserialize_product(data: dict[str, Any]) -> ProductRefView:
    return ProductRefView(
        oid=ProductID(uuid.UUID(data["oid"])),
        name=data["name"],
    )


def _deserialize_collaboration(
    data: dict[str, Any] | None,
) -> CollaborationSnapshotView | None:
    if data is None:
        return None
    return CollaborationSnapshotView(
        status=CollaborationStatus(data["status"]),
        accepted_at=(
            datetime.fromisoformat(data["accepted_at"])
            if data.get("accepted_at")
            else None
        ),
        declined_at=(
            datetime.fromisoformat(data["declined_at"])
            if data.get("declined_at")
            else None
        ),
        revoked_at=(
            datetime.fromisoformat(data["revoked_at"])
            if data.get("revoked_at")
            else None
        ),
        invite_expires_at=(
            datetime.fromisoformat(data["invite_expires_at"])
            if data.get("invite_expires_at")
            else None
        ),
    )


def _deserialize_details(
    data: dict[str, Any],
) -> NotificationDetailsView:
    type_ = data["type"]
    if type_ == "invite_sent":
        return InviteSentView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=_deserialize_product(data["product"]),
            collaboration=_deserialize_collaboration(data.get("collaboration")),
        )
    if type_ == "invite_accepted":
        collaborator = _deserialize_actor(data["collaborator"])
        if collaborator is None:
            raise ValueError("invite_accepted requires collaborator")
        return InviteAcceptedView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=_deserialize_product(data["product"]),
            collaborator=collaborator,
            collaboration=_deserialize_collaboration(data.get("collaboration")),
            viewer_can_manage_collaborators=bool(
                data.get("viewer_can_manage_collaborators", False),
            ),
        )
    if type_ == "invite_declined":
        decliner = _deserialize_actor(data["decliner"])
        if decliner is None:
            raise ValueError("invite_declined requires decliner")
        return InviteDeclinedView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=_deserialize_product(data["product"]),
            decliner=decliner,
            collaboration=_deserialize_collaboration(data.get("collaboration")),
            viewer_can_manage_collaborators=bool(
                data.get("viewer_can_manage_collaborators", False),
            ),
        )
    if type_ == "access_revoked":
        revoker = _deserialize_actor(data["revoker"])
        if revoker is None:
            raise ValueError("access_revoked requires revoker")
        return AccessRevokedView(
            collaboration_id=ProductCollaborationID(
                uuid.UUID(data["collaboration_id"]),
            ),
            product=_deserialize_product(data["product"]),
            revoker=revoker,
        )
    raise NotImplementedError(f"Unknown details type: {type_!r}")


def _deserialize_notification(data: dict[str, Any]) -> NotificationView:
    return NotificationView(
        oid=NotificationID(uuid.UUID(data["oid"])),
        recipient_id=UserID(uuid.UUID(data["recipient_id"])),
        kind=NotificationKind(data["kind"]),
        category=NotificationCategory(data["category"]),
        actor=_deserialize_actor(data["actor"]),
        created_at=datetime.fromisoformat(data["created_at"]),
        read_at=(
            datetime.fromisoformat(data["read_at"])
            if data.get("read_at")
            else None
        ),
        details=_deserialize_details(data["details"]),
    )


def _deserialize(raw: Any) -> NotificationEvent:  # noqa: ANN401
    payload = json.loads(raw)
    kind = NotificationEventKind(payload["kind"])
    if kind is NotificationEventKind.CREATED:
        notification = (
            _deserialize_notification(payload["notification"])
            if payload.get("notification") is not None
            else None
        )
        return NotificationCreatedEvent(notification=notification)
    if kind is NotificationEventKind.UPDATED:
        return NotificationUpdatedEvent(
            notification=_deserialize_notification(payload["notification"]),
        )
    if kind is NotificationEventKind.READ:
        return NotificationReadEvent(
            notification_id=NotificationID(
                uuid.UUID(payload["notification_id"]),
            ),
        )
    if kind is NotificationEventKind.READ_ALL:
        return NotificationReadAllEvent()
    raise NotImplementedError(f"Unknown event kind: {kind!r}")


class NotificationEventBusRedis(NotificationEventBus):
    """Redis pub/sub implementation of :class:`NotificationEventBus`.

    Channel-per-recipient (``notif:{user_id}``) so a connected
    user only wakes up on their own deltas. Same shape as
    :class:`ProductEventBusRedis` — kept duplicated rather than
    abstracted because the cross-bus payload contracts diverge.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def publish(
        self,
        recipient_id: UserID,
        event: NotificationEvent,
    ) -> None:
        await self._redis.publish(_channel(recipient_id), _serialize(event))

    @override
    async def subscribe(
        self,
        recipient_id: UserID,
    ) -> AsyncIterator[NotificationEvent]:
        channel = _channel(recipient_id)
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                yield _deserialize(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]
