from typing import Protocol

from learnic.application.common.notifications.views import (
    NotificationCounters,
    NotificationListPage,
    NotificationView,
)
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.notification.ids import NotificationID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


class NotificationReader(Protocol):
    """Read-side queries returning :class:`NotificationView`.

    The reader hydrates the polymorphic ``details`` view per row by
    joining the matching ``notification_<kind>`` subtype table and
    the referenced product / actor in the same query batch. Two
    fetches: one for the base + ``IN``-batched subtypes, then one
    follow-up for the actor / product refs.
    """

    async def list_for(
        self,
        recipient_id: UserID,
        category: NotificationCategory | None,
        cursor: str | None,
        limit: int,
    ) -> NotificationListPage: ...

    async def with_id(
        self,
        recipient_id: UserID,
        oid: NotificationID,
    ) -> NotificationView | None:
        """Fully hydrate a single notification.

        Used by command handlers (``MarkAsRead``) to publish the
        post-mutation view over the WebSocket channel and by the
        invite-publishing flow that needs to ship the new card to
        the recipient without an extra round-trip.
        """
        ...

    async def list_invite_sent_for_collaboration(
        self,
        recipient_id: UserID,
        collaboration_id: ProductCollaborationID,
    ) -> tuple[NotificationView, ...]:
        """Return every ``invite_sent`` view for ``(recipient, collaboration)``.

        Used by :class:`NotificationPublisher` to republish the
        recipient's invitation cards after the underlying
        collaboration changes status (accept / decline / revoke) so
        the panel re-renders the embedded snapshot without a
        full-list refetch.
        """
        ...

    async def counters_for(
        self,
        recipient_id: UserID,
    ) -> NotificationCounters: ...
