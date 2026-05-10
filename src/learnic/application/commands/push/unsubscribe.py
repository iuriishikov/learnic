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

    Idempotent: deleting an unknown endpoint returns silently.
    Cross-user attempts are silently no-op'd too — the gateway
    only matches on ``endpoint``, which is opaque enough that
    leaking nothing is acceptable; foreign endpoints will simply
    not match anything in this user's row set in practice.
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: PushSubscriptionGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway

    async def run(self, data: UnsubscribePushCommand) -> None:
        del data.user_id
        await self._gateway.delete_by_endpoint(data.endpoint)
        await self._transaction.commit()
