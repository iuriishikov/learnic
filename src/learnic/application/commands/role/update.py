from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    EntityNotFoundError,
    RoleNameAlreadyTakenError,
)
from learnic.application.common.persistence.role import RoleGateway, RoleSaver
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.role.errors import (
    CannotGrantPermissionsBeyondOwnSetError,
)
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import Permission, expand_implied
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleDescription,
    RoleName,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateCustomRoleCommand:
    """Optional-field update — ``None`` means "leave unchanged".

    ``description`` uses a sentinel pattern: the optional outer wrap
    distinguishes "not provided" (``None``) from "explicitly clear"
    (``Some(None)``). This rare-in-this-codebase pattern is justified
    here because role descriptions can be intentionally cleared.
    """

    actor_id: UserID
    role_id: RoleID
    name: str | None
    permissions: frozenset[Permission] | None
    description: str | None
    clear_description: bool


@final
class UpdateCustomRoleCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        role_gateway: RoleGateway,
        role_saver: RoleSaver,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._role_gateway: Final = role_gateway
        self._role_saver: Final = role_saver

    async def run(self, data: UpdateCustomRoleCommand) -> None:
        role = await self._role_gateway.with_id(data.role_id)
        if role is None or role.product_id is None:
            raise EntityNotFoundError(data.role_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(role.product_id),
            Permission.MANAGE_ROLES,
        )
        if data.name is not None and data.name != role.name.value:
            existing = await self._role_gateway.with_name_for_product(
                role.product_id,
                data.name,
            )
            if existing is not None and existing.oid != role.oid:
                raise RoleNameAlreadyTakenError(
                    role.product_id,
                    data.name,
                )
            role.rename(RoleName(data.name))
        if data.clear_description:
            role.update_description(None)
        elif data.description is not None:
            role.update_description(RoleDescription(data.description))
        permissions_changed = False
        if data.permissions is not None:
            actor_perms = await self._authorizer.effective_permissions(
                data.actor_id,
                AuthzTarget.for_product(role.product_id),
            )
            requested = expand_implied(frozenset(data.permissions))
            if (
                actor_perms is None
                or not requested.issubset(actor_perms.permissions)
            ):
                raise CannotGrantPermissionsBeyondOwnSetError
            role.update_permissions(PermissionSet(data.permissions))
            permissions_changed = True
        if permissions_changed:
            await self._role_saver.replace_permissions(role)
        await self._transaction.commit()
