from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GrantAdminCommand:
    user_id: UserID


@final
class GrantAdminCommandHandler:
    """Promote a user to platform administrator.

    Invoked from the ``grant-admin`` CLI command (there is no
    self-service HTTP route to mint admins — bootstrapping the first
    admin must happen out-of-band). Idempotent: re-granting an
    existing admin commits a no-op change.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(self, data: GrantAdminCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        user.grant_admin()
        await self._transaction.commit()
