from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    EntityNotFoundError,
    RoleInUseError,
)
from learnic.application.common.persistence.role import RoleGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeleteCustomRoleCommand:
    actor_id: UserID
    role_id: RoleID


@final
class DeleteCustomRoleCommandHandler:
    """Delete a custom role, refusing if any grant still references it.

    The DB enforces the same invariant via
    ``ON DELETE RESTRICT`` on ``collaboration_grants.role_id``; the
    in-app pre-check turns that into a typed
    :class:`RoleInUseError` (HTTP 409) instead of a raw
    IntegrityError.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        role_gateway: RoleGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._role_gateway: Final = role_gateway

    async def run(self, data: DeleteCustomRoleCommand) -> None:
        role = await self._role_gateway.with_id(data.role_id)
        if role is None:
            raise EntityNotFoundError(data.role_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(role.product_id),
            Permission.MANAGE_ROLES,
        )
        if await self._role_gateway.is_in_use(role.oid):
            raise RoleInUseError(role.oid)
        await self._role_gateway.delete(role)
        await self._transaction.commit()
