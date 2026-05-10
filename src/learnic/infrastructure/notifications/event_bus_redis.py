import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any, Final, cast

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
from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
)
from learnic.application.common.notifications.views import (
    NotificationDetailsView,
    NotificationView,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationKind,
)
from learnic.entities.notification.ids import NotificationID
from learnic.entities.user.models import UserID
from learnic.infrastructure.notifications.specs._helpers import (
    deserialize_actor,
    serialize_actor,
)


def _channel(recipient_id: UserID) -> str:
    return f"notif:{recipient_id}"


class NotificationEventBusRedis(NotificationEventBus):
    """Redis pub/sub implementation of :class:`NotificationEventBus`.

    Channel-per-recipient (``notif:{user_id}``) so a connected
    user only wakes up on their own deltas. Per-kind serialization
    is dispatched through :class:`NotificationKindRegistry`, so
    adding a new kind never touches this class.
    """

    def __init__(
        self,
        redis: Redis,
        kind_registry: NotificationKindRegistry,
    ) -> None:
        self._redis: Final = redis
        self._kinds: Final = kind_registry

    @override
    async def publish(
        self,
        recipient_id: UserID,
        event: NotificationEvent,
    ) -> None:
        await self._redis.publish(
            _channel(recipient_id),
            self._serialize(event),
        )

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
                yield self._deserialize(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    # --------------------------- internals --------------------------- #

    def _serialize(self, event: NotificationEvent) -> str:
        if isinstance(event, NotificationCreatedEvent):
            return json.dumps(
                {
                    "kind": NotificationEventKind.CREATED.value,
                    "notification": (
                        self._serialize_notification(event.notification)
                        if event.notification is not None
                        else None
                    ),
                },
            )
        if isinstance(event, NotificationUpdatedEvent):
            return json.dumps(
                {
                    "kind": NotificationEventKind.UPDATED.value,
                    "notification": self._serialize_notification(
                        event.notification,
                    ),
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

    def _serialize_notification(
        self,
        view: NotificationView,
    ) -> dict[str, Any]:
        return {
            "oid": str(view.oid),
            "recipient_id": str(view.recipient_id),
            "kind": view.kind.value,
            "category": view.category.value,
            "actor": serialize_actor(view.actor),
            "created_at": view.created_at.isoformat(),
            "read_at": view.read_at.isoformat() if view.read_at else None,
            "details": self._serialize_details(view.details),
        }

    def _serialize_details(
        self,
        details: NotificationDetailsView,
    ) -> dict[str, Any]:
        spec = self._kinds.by_view(details)
        return {"type": spec.kind.value, **spec.serialize_view(details)}

    def _deserialize(self, raw: Any) -> NotificationEvent:  # noqa: ANN401
        payload = json.loads(raw)
        kind = NotificationEventKind(payload["kind"])
        if kind is NotificationEventKind.CREATED:
            notification = (
                self._deserialize_notification(payload["notification"])
                if payload.get("notification") is not None
                else None
            )
            return NotificationCreatedEvent(notification=notification)
        if kind is NotificationEventKind.UPDATED:
            return NotificationUpdatedEvent(
                notification=self._deserialize_notification(
                    payload["notification"],
                ),
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

    def _deserialize_notification(
        self,
        data: dict[str, Any],
    ) -> NotificationView:
        return NotificationView(
            oid=NotificationID(uuid.UUID(data["oid"])),
            recipient_id=UserID(uuid.UUID(data["recipient_id"])),
            kind=NotificationKind(data["kind"]),
            category=NotificationCategory(data["category"]),
            actor=deserialize_actor(data["actor"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            read_at=(
                datetime.fromisoformat(data["read_at"]) if data.get("read_at") else None
            ),
            details=self._deserialize_details(data["details"]),
        )

    def _deserialize_details(
        self,
        data: dict[str, Any],
    ) -> NotificationDetailsView:
        kind = NotificationKind(data["type"])
        spec = self._kinds.by_kind(kind)
        return cast("NotificationDetailsView", spec.deserialize_view(data))
