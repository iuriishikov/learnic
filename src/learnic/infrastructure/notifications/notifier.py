import logging
from collections.abc import Mapping
from typing import Final, final

from typing_extensions import override

from learnic.application.common.notification_preferences.reader import (
    NotificationPreferencesReader,
)
from learnic.application.common.notifications.channels import (
    ChannelPayload,
    DeliveryChannel,
)
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.user.models import UserID

_logger = logging.getLogger(__name__)


@final
class NotifierService(Notifier):
    """Reuses the per-channel ``DeliveryChannel`` adapters from the
    publisher path — same email task, same web-push task. The only
    difference is no persisted ``Notification`` row and no in-app
    WS event (the recipient sees nothing in the bell-icon panel).

    Drops :data:`NotificationChannel.IN_APP` payloads if a caller
    accidentally includes one — the in-app surface requires a
    persisted view and is handled by :class:`NotificationPublisher`.
    """

    def __init__(
        self,
        preferences: NotificationPreferencesReader,
        user_gateway: UserGateway,
        channels: Mapping[NotificationChannel, DeliveryChannel],
    ) -> None:
        self._preferences: Final = preferences
        self._user_gateway: Final = user_gateway
        self._channels: Final = channels

    @override
    async def send(
        self,
        recipient_id: UserID,
        category: NotificationCategory,
        payloads: Mapping[NotificationChannel, ChannelPayload],
    ) -> None:
        recipient = await self._user_gateway.with_id(recipient_id)
        if recipient is None:
            return
        for channel_name, payload in payloads.items():
            if channel_name is NotificationChannel.IN_APP:
                # In-app needs a persisted view — caller should use
                # NotificationPublisher instead. Skip silently.
                continue
            try:
                enabled = await self._preferences.is_channel_enabled(
                    recipient_id,
                    channel_name,
                    category,
                )
                if not enabled:
                    continue
                channel = self._channels.get(channel_name)
                if channel is None:
                    continue
                await channel.deliver(recipient, payload)
            except Exception:
                _logger.exception(
                    "Notifier: channel %s failed for recipient %s",
                    channel_name.value,
                    recipient_id,
                )
