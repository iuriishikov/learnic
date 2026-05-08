from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from learnic.application.common.notifications.views import NotificationView
from learnic.entities.notification.ids import NotificationID
from learnic.entities.user.models import UserID


class NotificationEventKind(StrEnum):
    """Discriminator for the per-user push channel.

    ``CREATED`` carries a fresh :class:`NotificationView` so the
    panel can prepend a hydrated card without an extra fetch.
    ``READ`` and ``READ_ALL`` flip the unread counter and the
    card's blue dot — the panel only needs the affected ids.
    """

    CREATED = "created"
    READ = "read"
    READ_ALL = "read_all"


@dataclass(slots=True, frozen=True)
class NotificationCreatedEvent:
    kind: NotificationEventKind = NotificationEventKind.CREATED
    notification: NotificationView | None = None


@dataclass(slots=True, frozen=True)
class NotificationReadEvent:
    notification_id: NotificationID
    kind: NotificationEventKind = NotificationEventKind.READ


@dataclass(slots=True, frozen=True)
class NotificationReadAllEvent:
    kind: NotificationEventKind = NotificationEventKind.READ_ALL


NotificationEvent = (
    NotificationCreatedEvent | NotificationReadEvent | NotificationReadAllEvent
)


class NotificationEventBus(Protocol):
    """Per-user pub/sub channel for notification deltas.

    Mirrors :class:`CollaborationEventBus` — Redis pub/sub keyed by
    ``recipient_id`` so a user opens exactly one socket to
    ``WS /me/notifications`` and watches it across processes. The
    publisher is called by command handlers right after commit;
    the subscriber lives in the WS endpoint.
    """

    async def publish(
        self,
        recipient_id: UserID,
        event: NotificationEvent,
    ) -> None: ...

    def subscribe(
        self,
        recipient_id: UserID,
    ) -> AsyncIterator[NotificationEvent]: ...
