import logging
from collections.abc import Mapping
from typing import Final, final

from learnic.application.common.notifications.channels import DeliveryChannel
from learnic.application.common.notification_preferences.reader import (
    NotificationPreferencesReader,
)
from learnic.application.common.notifications.event_bus import (
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
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID

_logger = logging.getLogger(__name__)


@final
class NotificationPublisher:
    """Persist a notification and fan it out across enabled channels.

    The dispatch is channel-agnostic: a list of :class:`DeliveryChannel`
    adapters is injected at construction, and every published
    notification iterates over them. Adding a new channel (SMS,
    Telegram, in-product banner) means writing a new ``DeliveryChannel``
    implementation and wiring it in IoC — no edits here, no edits
    to spec classes that don't care about the new channel.

    Per-recipient channel selection still goes through
    :class:`NotificationPreferencesReader`. The always-on
    :data:`NotificationChannel.IN_APP` channel bypasses the reader
    (it cannot be disabled). Channels for which the recipient's
    preference matrix says "off" — and channels for which the
    spec's :meth:`render` returns ``None`` — are skipped silently.

    Failures inside an individual channel must not roll back the
    source command; each channel adapter is expected to log and
    swallow its own errors so siblings still deliver.

    :meth:`republish_for_collaboration` re-hydrates the recipient's
    surviving ``invite_sent`` card(s) for a collaboration whose
    status just changed and emits the ``updated`` envelope so panels
    patch the embedded snapshot in place — independent of the
    delivery-channel fan-out above.
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: NotificationGateway,
        reader: NotificationReader,
        event_bus: NotificationEventBus,
        preferences: NotificationPreferencesReader,
        kind_registry: NotificationKindRegistry,
        user_gateway: UserGateway,
        channels: Mapping[NotificationChannel, DeliveryChannel],
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway
        self._reader: Final = reader
        self._event_bus: Final = event_bus
        self._preferences: Final = preferences
        self._kinds: Final = kind_registry
        self._user_gateway: Final = user_gateway
        self._channels: Final = channels

    async def publish(self, notification: Notification) -> None:
        await self._gateway.add(notification)
        await self._transaction.commit()
        view = await self._reader.with_id(
            notification.recipient_id,
            notification.oid,
        )
        if view is None:
            return
        recipient = await self._user_gateway.with_id(notification.recipient_id)
        if recipient is None:
            return

        spec = self._kinds.by_kind(notification.kind)

        for channel_name, channel in self._channels.items():
            try:
                if not await self._is_channel_enabled(
                    notification.recipient_id,
                    channel_name,
                    notification.category,
                ):
                    continue
                payload = spec.render(channel_name, view)
                if payload is None:
                    continue
                await channel.deliver(recipient, payload)
            except Exception:
                _logger.exception(
                    "Channel %s failed for notification %s",
                    channel_name.value,
                    notification.oid,
                )

    async def _is_channel_enabled(
        self,
        recipient_id: UserID,
        channel: NotificationChannel,
        category: NotificationCategory,
    ) -> bool:
        # The in-app surface is the always-on bell-icon panel —
        # user preferences cannot opt out of it.
        if channel is NotificationChannel.IN_APP:
            return True
        return await self._preferences.is_channel_enabled(
            recipient_id,
            channel,
            category,
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
