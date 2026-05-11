import logging
from typing import Final, final

from typing_extensions import override

from learnic.application.common.notifications.channels import (
    ChannelPayload,
    DeliveryChannel,
    InAppPayload,
)
from learnic.application.common.notifications.event_bus import (
    NotificationCreatedEvent,
    NotificationEventBus,
)
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.user.models import User

_logger = logging.getLogger(__name__)


@final
class InAppChannel(DeliveryChannel):
    """In-app delivery channel — publishes a ``CREATED`` event on the WS bus.

    Always enabled (cannot be disabled in user preferences) — the
    bell-icon panel is the always-on surface. The hydrated view is
    carried on the payload so this channel does not need to re-read
    it.
    """

    name = NotificationChannel.IN_APP

    def __init__(self, event_bus: NotificationEventBus) -> None:
        self._event_bus: Final = event_bus

    @override
    async def deliver(
        self,
        recipient: User,
        payload: ChannelPayload,
    ) -> None:
        if not isinstance(payload, InAppPayload):
            return
        try:
            await self._event_bus.publish(
                recipient.oid,
                NotificationCreatedEvent(notification=payload.view),
            )
        except Exception:
            _logger.exception(
                "InAppChannel delivery failed for recipient %s",
                recipient.oid,
            )
