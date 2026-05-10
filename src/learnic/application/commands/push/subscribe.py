from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.push.gateway import PushSubscriptionGateway
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
        subscription = PushSubscription.create(
            user_id=data.user_id,
            endpoint=data.endpoint,
            p256dh=data.p256dh,
            auth=data.auth,
            user_agent=data.user_agent,
        )
        await self._gateway.upsert(subscription)
        await self._transaction.commit()
