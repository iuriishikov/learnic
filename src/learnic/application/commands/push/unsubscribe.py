from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.push.gateway import PushSubscriptionGateway
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UnsubscribePushCommand:
    user_id: UserID
    endpoint: str


@final
class UnsubscribePushCommandHandler:
    """Drop a Web Push subscription owned by the caller.

    Idempotent: deleting an unknown endpoint returns silently. The
    delete is scoped to the authenticated ``user_id`` so a caller can
    never remove another user's subscription by presenting its
    endpoint string (which, while opaque, can leak via shared devices
    or logs).
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: PushSubscriptionGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway

    async def run(self, data: UnsubscribePushCommand) -> None:
        await self._gateway.delete_by_endpoint(data.endpoint, data.user_id)
        await self._transaction.commit()
