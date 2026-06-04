from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    EntityNotFoundError,
    RoleNameAlreadyTakenError,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.role import (
    RoleGateway,
    RoleReader,
    RoleSaver,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    ProductEventBus,
    RoleCreatedPayload,
    publish_product_event,
)
from learnic.entities.common.limits import ROLE_LIMIT
from learnic.entities.product.ids import ProductID
from learnic.entities.role.errors import (
    CannotGrantPermissionsBeyondOwnSetError,
)
from learnic.entities.role.ids import RoleID
from learnic.entities.role.models import Role
from learnic.entities.role.permissions import Permission, expand_implied
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleDescription,
    RoleName,
    RolePosition,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CreateCustomRoleCommand:
    actor_id: UserID
    product_id: ProductID
    name: str
    permissions: frozenset[Permission]
    description: str | None


@final
class CreateCustomRoleCommandHandler:
    """Create a per-product custom role.

    Authorization: caller must hold ``MANAGE_ROLES`` on the product
    (or own it). The product must exist; the role name must be
    unique within that product (the unique index on
    ``(product_id, name)`` would catch duplicates as well, but the
    in-app pre-check turns the conflict into a clean
    :class:`RoleNameAlreadyTakenError` instead of a generic IntegrityError).
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        role_gateway: RoleGateway,
        role_reader: RoleReader,
        role_saver: RoleSaver,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._role_gateway: Final = role_gateway
        self._role_reader: Final = role_reader
        self._role_saver: Final = role_saver
        self._event_bus: Final = event_bus

    async def run(self, data: CreateCustomRoleCommand) -> RoleID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_ROLES,
        )
        # Privilege-escalation guard: the new role's permission set must
        # be a subset of the actor's effective permissions on this
        # product. The product owner — who has every permission by
        # short-circuit — is implicitly allowed.
        actor_perms = await self._authorizer.effective_permissions(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
        )
        requested = expand_implied(frozenset(data.permissions))
        if actor_perms is None or not requested.issubset(actor_perms.permissions):
            raise CannotGrantPermissionsBeyondOwnSetError
        existing = await self._role_gateway.with_name_for_product(
            data.product_id,
            data.name,
        )
        if existing is not None:
            raise RoleNameAlreadyTakenError(data.product_id, data.name)
        ROLE_LIMIT.ensure(
            await self._role_reader.count_for_product(data.product_id),
        )
        # New custom role slots at the very bottom of the product's
        # current hierarchy so it cannot accidentally outrank existing
        # collaborators.
        max_position = await self._role_reader.max_position_in_product(
            data.product_id,
        )
        role = Role.create_custom(
            product_id=data.product_id,
            name=RoleName(data.name),
            permissions=PermissionSet(data.permissions),
            position=RolePosition(max_position + 10),
            created_by=data.actor_id,
            description=(
                RoleDescription(data.description)
                if data.description is not None
                else None
            ),
        )
        await self._role_saver.save(role)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=RoleCreatedPayload.from_entity(role),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        return role.oid
