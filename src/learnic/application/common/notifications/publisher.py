import logging
from typing import Final, final

from learnic.application.common.notification_preferences.reader import (
    NotificationPreferencesReader,
)
from learnic.application.common.notifications.event_bus import (
    NotificationCreatedEvent,
    NotificationEventBus,
    NotificationUpdatedEvent,
)
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.notification.models import Notification
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID

_logger = logging.getLogger(__name__)


@final
class NotificationPublisher:
    """Persist a notification and push it to the recipient's WS channel.

    Producers (existing command handlers like
    ``InviteCollaboratorByUserCommandHandler``) call
    :meth:`publish` **after** their primary transaction commits.
    The publisher opens its own commit cycle for the notification
    row, hydrates a :class:`NotificationView` via the reader, and
    forwards it on the per-user pub/sub channel — same pattern as
    ``publish_product_event`` but with persistence in the middle.

    :meth:`republish_for_collaboration` re-hydrates the recipient's
    surviving ``invite_sent`` card(s) for a collaboration whose
    status just changed (accept / decline / revoke) and emits the
    ``updated`` envelope so panels patch the embedded snapshot in
    place. The notification rows themselves are immutable —
    everything dynamic lives in the joined collaboration row.

    Failures here are isolated from the source command — a Redis
    or Postgres hiccup must not roll back the original invite. The
    caller is expected to wrap the call in a try/except and log;
    keeping the notification orchestration here avoids leaking
    it into every command handler.
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: NotificationGateway,
        reader: NotificationReader,
        event_bus: NotificationEventBus,
        preferences: NotificationPreferencesReader,
        scheduler: TaskScheduler,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway
        self._reader: Final = reader
        self._event_bus: Final = event_bus
        self._preferences: Final = preferences
        self._scheduler: Final = scheduler

    async def publish(self, notification: Notification) -> None:
        await self._gateway.add(notification)
        await self._transaction.commit()
        view = await self._reader.with_id(
            notification.recipient_id,
            notification.oid,
        )
        if view is None:
            return
        await self._event_bus.publish(
            notification.recipient_id,
            NotificationCreatedEvent(notification=view),
        )
        await self._dispatch_push(notification)

    async def _dispatch_push(self, notification: Notification) -> None:
        """Schedule a Web Push delivery for the recipient if opted in.

        Real preference enforcement: the publisher reads the
        recipient's matrix and only enqueues the fanout task when
        push is enabled for this category. The worker re-checks
        the preference too — defence in depth — so a stale enqueue
        can't bypass an opt-out flipped between commit and consume.
        """
        try:
            push_enabled = await self._preferences.is_channel_enabled(
                notification.recipient_id,
                NotificationChannel.PUSH,
                notification.category,
            )
            if not push_enabled:
                return
            title, body = _render_push_text(notification)
            await self._scheduler.schedule_send_web_push(
                user_id=notification.recipient_id,
                title=title,
                body=body,
                category=notification.category.value,
                tag=str(notification.oid),
                bypass_preferences=False,
            )
        except Exception:
            _logger.exception(
                "Web Push dispatch failed for notification %s",
                notification.oid,
            )

    async def republish_for_collaboration(
        self,
        recipient_id: UserID,
        collaboration_id: ProductCollaborationID,
    ) -> None:
        views = await self._reader.list_invite_sent_for_collaboration(
            recipient_id,
            collaboration_id,
        )
        for view in views:
            await self._event_bus.publish(
                recipient_id,
                NotificationUpdatedEvent(notification=view),
            )


def _render_push_text(notification: Notification) -> tuple[str, str]:
    """Render the system-banner copy from a notification entity.

    Kept tiny and kind-aware on purpose — email/web-push copy
    rendering belongs in a templating module long-term, but the
    in-app categories have stable wording so a switch keeps the
    publisher self-contained for now.
    """
    from learnic.entities.notification.enums import NotificationKind

    if notification.kind is NotificationKind.INVITE_SENT:
        return (
            "New collaboration invite",
            "You have been invited to collaborate on a product.",
        )
    if notification.kind is NotificationKind.INVITE_ACCEPTED:
        return (
            "Invite accepted",
            "Your collaboration invite was accepted.",
        )
    if notification.kind is NotificationKind.INVITE_DECLINED:
        return (
            "Invite declined",
            "Your collaboration invite was declined.",
        )
    if notification.kind is NotificationKind.ACCESS_REVOKED:
        return (
            "Access revoked",
            "Your access to a product was revoked.",
        )
    return ("New notification", "Open the app to see the details.")
