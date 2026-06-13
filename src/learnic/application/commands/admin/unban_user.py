from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UnbanUserCommand:
    user_id: UserID


@final
class UnbanUserCommandHandler:
    """Lift a user's ban so they can log in again.

    The inverse of :class:`BanUserCommandHandler`. Clearing the
    ``is_banned`` flag is all that is required — the original ban
    already revoked the user's refresh-token families, so the user
    simply logs in afresh; there are no sessions to restore.
    Idempotent: unbanning a user who is not banned commits a no-op.

    Authorization (admin-only) is enforced at the HTTP boundary by
    ``AdminAuthenticator``.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(self, data: UnbanUserCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        user.unban()
        await self._transaction.commit()
