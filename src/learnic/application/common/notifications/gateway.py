from typing import Protocol

from learnic.entities.notification.ids import NotificationID
from learnic.entities.notification.models import Notification


class NotificationGateway(Protocol):
    """Write-side persistence for :class:`Notification` aggregates.

    The implementation is responsible for persisting both the parent
    ``notification`` row and the appropriate ``notification_<kind>``
    subtype row in a single unit of work — option B persistence
    enforces the link via a composite ``(notification_id, kind)``
    foreign key, but the entity must exist on both sides for the
    constraint to hold.

    Lookups (``with_id``) hydrate the polymorphic ``details`` by
    loading the matching subtype row.
    """

    async def add(self, notification: Notification) -> None: ...

    async def with_id(
        self,
        oid: NotificationID,
    ) -> Notification | None: ...

    async def update_read_state(
        self,
        notification: Notification,
    ) -> None:
        """Persist ``read_at`` after a successful :meth:`mark_read`.

        Keeps the write surface tiny — read-state changes are the
        only mutation supported on persisted notifications.
        """
        ...

    async def mark_all_read(self, recipient_id: object) -> int:
        """Mark every unread notification of ``recipient_id`` as read.

        Returns the affected row count so the caller can short-circuit
        the WebSocket push when nothing changed.
        """
        ...
