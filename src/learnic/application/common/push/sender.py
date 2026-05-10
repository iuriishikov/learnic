from typing import Protocol

from learnic.application.common.push.payload import PushPayload
from learnic.entities.push_subscription.models import PushSubscription


class PushDeliveryResult(Protocol):
    """Outcome of one ``PushSender.send`` invocation.

    The worker uses ``is_gone`` to drop subscriptions whose endpoint
    was permanently rejected (HTTP 404 or 410 from the push service)
    so the next delivery never wastes a round-trip on stale rows.
    Other failures are transient — caller logs and moves on.
    """

    @property
    def is_gone(self) -> bool: ...

    @property
    def status_code(self) -> int | None: ...


class PushSender(Protocol):
    """Outbound transport for a single Web Push subscription.

    Implementations sign each delivery with the configured VAPID
    keypair and POST to the browser-vendor endpoint embedded in
    the subscription. The protocol is a thin abstraction so the
    application layer can stay vendor-neutral: the same handler
    works against any compliant push service (FCM, autopush, APNs)
    because the endpoint is what the browser hands us, not what
    the backend chooses.
    """

    async def send(
        self,
        subscription: PushSubscription,
        payload: PushPayload,
    ) -> PushDeliveryResult: ...
