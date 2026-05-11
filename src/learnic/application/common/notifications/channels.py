"""Per-channel payloads and the ``DeliveryChannel`` Protocol.

A delivery channel turns a notification's per-channel payload into
an actual outbound message (email task enqueued, push task enqueued,
WS event published). Channels are the only place that knows about
TaskScheduler / EventBus details — handlers and the dispatcher don't.

Adding a new channel (SMS, Telegram, in-product banner) means:

1. Add a new ``ChannelPayload`` subclass declaring its payload shape.
2. Add the new variant to :class:`NotificationChannel` and decide
   whether it should appear in the user preferences matrix.
3. Implement a ``DeliveryChannel`` for it and register it in IoC.
4. Optionally extend :class:`NotificationKindSpec.render` (or the
   per-spec ``render(channel)``) so kinds that care produce a
   payload — kinds that don't return ``None`` and the channel
   skips them silently.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from learnic.application.common.email.components import EmailComponent
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.user.models import User


@dataclass(slots=True, frozen=True)
class EmailPayload:
    """What an email-channel delivery needs from the spec."""

    subject: str
    components: Sequence[EmailComponent]


@dataclass(slots=True, frozen=True)
class PushPayload:
    """What a web-push delivery needs from the spec.

    ``category`` is carried so the worker can re-check the user's
    push-preference at consume time (defence in depth against an
    opt-out flipped between commit and delivery).
    """

    title: str
    body: str
    category: str
    url: str | None = None
    icon: str | None = None


@dataclass(slots=True, frozen=True)
class InAppPayload:
    """Payload for the always-on in-app channel.

    Carries the hydrated :class:`NotificationView` so the channel
    can publish it on the WS bus without re-fetching. ``view`` is
    typed loosely as :class:`Any` to avoid a circular import with
    the views module — the WS channel re-imports the concrete type
    at the call site.
    """

    view: Any


ChannelPayload = EmailPayload | PushPayload | InAppPayload


class DeliveryChannel(Protocol):
    """One outbound channel — email, web-push, in-app, future SMS / Telegram.

    Channels are stateless adapters owning their TaskScheduler /
    EventBus dependency. The dispatcher iterates over the channels
    enabled for the recipient + category and calls :meth:`deliver`
    on each; channels that don't receive a payload skip silently.
    """

    name: NotificationChannel

    async def deliver(
        self,
        recipient: User,
        payload: ChannelPayload,
    ) -> None:
        """Send ``payload`` to ``recipient`` through this channel.

        Implementations isolate the per-channel transport (broker
        task, WS publish, third-party API call). Failures must be
        logged and swallowed — one channel's hiccup must not roll
        back the source command or skip the remaining channels.
        """
        ...
