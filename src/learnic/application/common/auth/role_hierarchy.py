"""Discord-style role hierarchy enforcement.

Sits next to :class:`Authorizer` and answers two questions:

1. Can ``actor`` assign / revoke a role at this position?
2. Can ``actor`` act on this target user (change their grants,
   revoke them, etc.)?

The rule is strict: ``actor.position < target.position``. Equality
is forbidden so two collaborators at the same rank cannot manage
each other and cannot grant their own role to anyone. The product
author has the synthetic top position (``OWNER_POSITION = 0``) and
outranks every real role.
"""

from typing import Final, Protocol

from learnic.application.common.persistence.role import RoleReader
from learnic.entities.product.ids import ProductID
from learnic.entities.role.constants import OWNER_POSITION
from learnic.entities.role.errors import RoleHierarchyViolationError
from learnic.entities.role.ids import RoleID
from learnic.entities.user.models import UserID


class RoleHierarchy(Protocol):
    """Contract for hierarchy-based authorization checks."""

    async def actor_position(
        self,
        product_id: ProductID,
        actor_id: UserID,
    ) -> int | None:
        """Return the actor's effective rank on ``product_id``.

        Returns :data:`OWNER_POSITION` (``0``) for the product
        author. For collaborators, returns ``min(position)`` over
        the user's active product-scope grants. Returns ``None``
        when the actor has no rank at all (not owner, not on team).
        """
        ...

    async def require_can_assign_roles(
        self,
        product_id: ProductID,
        actor_id: UserID,
        role_ids: list[RoleID],
    ) -> None:
        """Raise if ``actor`` cannot grant any of ``role_ids``.

        Each role's stored ``position`` must be strictly greater
        than the actor's effective position. Owner can assign every
        role.
        """
        ...

    async def require_can_act_on_user(
        self,
        product_id: ProductID,
        actor_id: UserID,
        target_user_id: UserID,
    ) -> None:
        """Raise if ``actor`` cannot manage ``target_user_id``.

        The actor's position must be strictly above the target's
        highest-rank role on the product. Targets with no active
        grant (e.g. an invited-by-email row not yet accepted) are
        allowed — only the role-assignment check applies there.
        """
        ...


class RoleHierarchyService(RoleHierarchy):
    """SQL-backed :class:`RoleHierarchy`.

    Reuses :class:`RoleReader` for the underlying lookups so the
    repository layer stays the single source of truth for role
    metadata; nothing here goes around it.
    """

    def __init__(
        self,
        reader: RoleReader,
        product_owner_resolver: "ProductOwnerResolver",
    ) -> None:
        self._reader: Final = reader
        self._owner_resolver: Final = product_owner_resolver

    async def actor_position(
        self,
        product_id: ProductID,
        actor_id: UserID,
    ) -> int | None:
        if await self._owner_resolver.is_owner(product_id, actor_id):
            return OWNER_POSITION
        return await self._reader.min_position_for_user(
            product_id,
            actor_id,
        )

    async def require_can_assign_roles(
        self,
        product_id: ProductID,
        actor_id: UserID,
        role_ids: list[RoleID],
    ) -> None:
        actor_pos = await self.actor_position(product_id, actor_id)
        if actor_pos is None:
            # No rank at all — this should never happen because the
            # MANAGE_COLLABORATORS check ran first, but keep the
            # belt-and-suspenders branch.
            raise RoleHierarchyViolationError
        if actor_pos == OWNER_POSITION:
            return
        for role_id in role_ids:
            role = await self._reader.with_id(role_id)
            if role is None:
                # Caller will surface as EntityNotFound separately.
                continue
            if role.position <= actor_pos:
                raise RoleHierarchyViolationError

    async def require_can_act_on_user(
        self,
        product_id: ProductID,
        actor_id: UserID,
        target_user_id: UserID,
    ) -> None:
        actor_pos = await self.actor_position(product_id, actor_id)
        if actor_pos is None:
            raise RoleHierarchyViolationError
        if actor_pos == OWNER_POSITION:
            return
        target_pos = await self._reader.min_position_for_user(
            product_id,
            target_user_id,
        )
        if target_pos is None:
            # Target has no active product-scope grant — invited but
            # not accepted, or only module/lesson scopes. Treat as
            # "no rank, anyone with MANAGE_COLLABORATORS can touch".
            return
        if actor_pos >= target_pos:
            raise RoleHierarchyViolationError


class ProductOwnerResolver(Protocol):
    """Tiny side-channel: was ``actor_id`` the author of ``product_id``?

    Exists so the hierarchy service does not need a direct dependency
    on :class:`ProductGateway` — that would pull a write-side
    aggregate into a read-heavy authorisation check. The DI-bound
    implementation in ``infrastructure/auth`` reuses the same SQL
    row that :class:`AuthorizerService` already loads.
    """

    async def is_owner(
        self,
        product_id: ProductID,
        user_id: UserID,
    ) -> bool: ...
