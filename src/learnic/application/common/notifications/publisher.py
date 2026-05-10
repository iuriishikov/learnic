import logging
from typing import Final, final

from learnic.application.common.email.components import EmailParagraph
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
from learnic.application.common.notifications.kind_spec import (
    NotificationKindRegistry,
)
from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
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
        kind_registry: NotificationKindRegistry,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway
        self._reader: Final = reader
        self._event_bus: Final = event_bus
        self._preferences: Final = preferences
        self._scheduler: Final = scheduler
        self._kinds: Final = kind_registry
        self._user_gateway: Final = user_gateway

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
        await self._dispatch_email(notification)

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
            spec = self._kinds.by_kind(notification.kind)
            title, body = spec.push_title, spec.push_body
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

    async def _dispatch_email(self, notification: Notification) -> None:
        """Schedule an email delivery for the recipient if opted in.

        Mirrors :meth:`_dispatch_push`: read the recipient's matrix at
        publish time and enqueue only when the email channel is enabled
        for this category. The publisher resolves the recipient's
        address and assembles the typed component list; the scheduler
        owns the render step and hands the rendered payload to the
        worker. Failures are isolated — an SMTP / broker hiccup must
        not roll back the source command.
        """
        try:
            email_enabled = await self._preferences.is_channel_enabled(
                notification.recipient_id,
                NotificationChannel.EMAIL,
                notification.category,
            )
            if not email_enabled:
                return
            user = await self._user_gateway.with_id(notification.recipient_id)
            if user is None:
                return
            spec = self._kinds.by_kind(notification.kind)
            await self._scheduler.schedule_send_email(
                to=user.email.value,
                subject=spec.email_subject,
                components=[EmailParagraph.text(spec.email_body)],
            )
        except Exception:
            _logger.exception(
                "Notification email dispatch failed for notification %s",
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
