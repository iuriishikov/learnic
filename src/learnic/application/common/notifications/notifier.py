"""Ad-hoc multi-channel notification dispatch (no persistence).

Handlers call :meth:`Notifier.send` with a payload map keyed by
:class:`NotificationChannel` and the dispatcher:

1. Resolves the recipient (one user gateway hit) — silently no-op
   if the user vanished between commit and notify.
2. For each channel in the map, checks the recipient's
   :class:`NotificationPreferencesReader` matrix for the supplied
   ``category`` and skips disabled channels.
3. Delegates delivery to the corresponding :class:`DeliveryChannel`.

This is the **transient** counterpart to :class:`NotificationPublisher`
— intended for one-shot events that should not land on the
bell-icon panel (email verification, password reset, security
alerts, owner-notification on `leave product`). When the event
should also persist as an in-app card, use ``NotificationPublisher``
instead.

``NotificationChannel.IN_APP`` payloads are silently dropped: the
in-app channel only makes sense behind ``NotificationPublisher``
because it needs a persisted :class:`NotificationView` to publish
on the WS bus.

Per-channel failures are logged and swallowed so a flake on one
delivery (email broker hiccup, push service 503) does not block
the remaining channels.
"""

from collections.abc import Mapping
from typing import Protocol

from learnic.application.common.notifications.channels import ChannelPayload
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.user.models import UserID


class Notifier(Protocol):
    """Application-layer entry point for ad-hoc multi-channel notifications.

    The implementation lives in ``infrastructure/notifications/``
    and adapts ``DeliveryChannel`` registrations from
    :class:`NotificationChannelsProvider`. Handlers depend on this
    Protocol so adding a new channel only requires wiring at the
    infrastructure layer — call sites stay the same.
    """

    async def send(
        self,
        recipient_id: UserID,
        category: NotificationCategory,
        payloads: Mapping[NotificationChannel, ChannelPayload],
    ) -> None: ...
