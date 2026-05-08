from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.notifications.event_bus import (
    NotificationEventBus,
    NotificationReadEvent,
)
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.notification.errors import AlreadyReadError
from learnic.entities.notification.ids import NotificationID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class MarkNotificationAsReadCommand:
    actor_id: UserID
    notification_id: NotificationID


@final
class MarkNotificationAsReadCommandHandler:
    """Mark one notification as read.

    Idempotent at the HTTP boundary — re-marking an already-read
    row returns ``204`` without re-publishing, so client double-
    clicks never produce duplicate WS pushes. Cross-recipient
    attempts surface as ``NotResourceOwnerError`` (HTTP 403); the
    caller learns nothing about whether the id exists for someone
    else.
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: NotificationGateway,
        event_bus: NotificationEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway
        self._event_bus: Final = event_bus

    async def run(self, data: MarkNotificationAsReadCommand) -> None:
        notification = await self._gateway.with_id(data.notification_id)
        if notification is None:
            raise EntityNotFoundError(data.notification_id)
        if notification.recipient_id != data.actor_id:
            raise NotResourceOwnerError(
                notification.oid,
                data.actor_id,
            )
        try:
            notification.mark_read()
        except AlreadyReadError:
            return
        await self._gateway.update_read_state(notification)
        await self._transaction.commit()
        await self._event_bus.publish(
            data.actor_id,
            NotificationReadEvent(notification_id=notification.oid),
        )
