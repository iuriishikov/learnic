from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.push.gateway import PushSubscriptionGateway
from learnic.entities.common.limits import PUSH_SUBSCRIPTION_LIMIT
from learnic.entities.push_subscription.models import PushSubscription
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SubscribePushCommand:
    user_id: UserID
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None


@final
class SubscribePushCommandHandler:
    """Register or refresh a Web Push subscription for the caller.

    Re-subscribing the same browser on the same device produces an
    identical ``endpoint`` string; the gateway upserts so the keys
    on file always match what the browser would expect on the next
    delivery. New ``endpoint`` strings (different device, or a
    rotated subscription) create a fresh row owned by the same user.
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: PushSubscriptionGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway

    async def run(self, data: SubscribePushCommand) -> None:
        existing = await self._gateway.list_for_user(data.user_id)
        # Refreshing a known endpoint (push-service rotation or a
        # re-subscribe on the same device) is an upsert and must never
        # 409 — only a brand-new endpoint adds a row, so only that path
        # counts toward the per-user device cap.
        is_new_device = all(
            sub.endpoint != data.endpoint for sub in existing
        )
        if is_new_device:
            PUSH_SUBSCRIPTION_LIMIT.ensure(len(existing))
        subscription = PushSubscription.create(
            user_id=data.user_id,
            endpoint=data.endpoint,
            p256dh=data.p256dh,
            auth=data.auth,
            user_agent=data.user_agent,
        )
        await self._gateway.upsert(subscription)
        await self._transaction.commit()
