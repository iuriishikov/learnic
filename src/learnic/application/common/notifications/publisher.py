from typing import Final, final

from learnic.application.common.notifications.event_bus import (
    NotificationCreatedEvent,
    NotificationEventBus,
)
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.notification.models import Notification


@final
class NotificationPublisher:
    """Persist a notification and push it to the recipient's WS channel.

    Producers (existing command handlers like
    ``InviteCollaboratorByUserCommandHandler``) call
    :meth:`publish` **after** their primary transaction commits.
    The publisher opens its own commit cycle for the notification
    row, hydrates a :class:`NotificationView` via the reader, and
    forwards it on the per-user pub/sub channel — same pattern as
    ``publish_collaboration_event`` but with persistence in the
    middle.

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
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway
        self._reader: Final = reader
        self._event_bus: Final = event_bus

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
