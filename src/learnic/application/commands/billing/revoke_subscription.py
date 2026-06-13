from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.billing import (
    SubscriptionGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RevokeSubscriptionCommand:
    """Admin revokes a user's paid/BETA access, dropping them to FREE."""

    user_id: UserID


@final
class RevokeSubscriptionCommandHandler:
    """Revoke every active grant a user holds, returning them to FREE.

    The inverse of :class:`GrantSubscriptionCommandHandler`. Revoking
    stamps ``revoked_at`` on each currently-active row rather than
    deleting it, so the audit trail of who-had-what-when is kept.
    All active grants are revoked (not just the latest) so an older
    overlapping grant cannot keep the user on an upgraded plan after
    the admin meant to remove access.

    Idempotent: a user already on FREE has no active grants, so the
    call commits a no-op and still succeeds. ``EntityNotFoundError``
    is raised only when the target user does not exist at all.

    Authorization (admin-only) is enforced at the HTTP boundary by
    ``AdminAuthenticator``.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        subscription_gateway: SubscriptionGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._subscription_gateway: Final = subscription_gateway

    async def run(self, data: RevokeSubscriptionCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        active = await self._subscription_gateway.active_for_user(
            data.user_id,
        )
        for subscription in active:
            subscription.revoke()
        await self._transaction.commit()
