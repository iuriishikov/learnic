from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.notifications.event_bus import (
    NotificationEventBus,
    NotificationReadAllEvent,
)
from learnic.application.common.notifications.gateway import (
    NotificationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class MarkAllNotificationsAsReadCommand:
    actor_id: UserID


@final
class MarkAllNotificationsAsReadCommandHandler:
    """Mark every unread notification of the caller as read.

    The double-check icon in the panel header. Skips the WebSocket
    push when the gateway reports zero affected rows so a click on
    an already-empty list does not nudge other tabs.
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

    async def run(self, data: MarkAllNotificationsAsReadCommand) -> None:
        affected = await self._gateway.mark_all_read(data.actor_id)
        await self._transaction.commit()
        if affected == 0:
            return
        await self._event_bus.publish(
            data.actor_id,
            NotificationReadAllEvent(),
        )
