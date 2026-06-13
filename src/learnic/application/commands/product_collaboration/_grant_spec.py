"""Shared helper for resolving collaboration-grant input.

Both ``InviteCollaborator*`` and ``UpdateCollaborationGrants`` accept
the same shape: a non-empty list of ``(role_id, scope_type, scope_id?)``
tuples. The helper validates them against the target product (role
must exist and belong to the same product; module/lesson scope ids
must reference resources inside the product) and converts them into
:class:`CollaborationGrant` entities.
"""

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.resource_lineage import (
    ResourceLineageReader,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.role import RoleGateway
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.errors import InvalidScopeError
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.role.errors import (
    CannotGrantPermissionsBeyondOwnSetError,
)
from learnic.entities.role.ids import RoleID
from learnic.entities.role.permissions import (
    Permission,
    ScopeType,
    expand_implied,
)
from learnic.entities.user.models import UserID


async def require_grants_within_actor_permissions(
    *,
    authorizer: Authorizer,
    role_gateway: RoleGateway,
    actor_id: UserID,
    product_id: ProductID,
    role_ids: list[RoleID],
) -> None:
    """Reject a grant that hands out permissions the actor lacks.

    Privilege-escalation guard for every collaboration grant-assignment
    path (invite-by-user / -email, update-grants, reinvite). Mirrors the
    role create/update guard: the union of the permissions carried by
    every role being granted, expanded through ``PERMISSION_IMPLIES``,
    must be a subset of the actor's own effective permissions on the
    product. The product owner — whose effective set is everything by
    short-circuit — always passes.

    The rank check (``RoleHierarchy.require_can_assign_roles``) is a
    separate, complementary gate: a role may sit below the actor's rank
    yet still carry a permission the actor does not hold, so both checks
    are required.

    Raises:
        CannotGrantPermissionsBeyondOwnSetError: A requested permission
            is outside the actor's effective set; HTTP 403.
    """
    actor_perms = await authorizer.effective_permissions(
        actor_id,
        AuthzTarget.for_product(product_id),
    )
    granted: set[Permission] = set()
    for role_id in role_ids:
        role = await role_gateway.with_id(role_id)
        if role is None or role.permissions is None:
            # Missing roles surface as EntityNotFound elsewhere; skip
            # them here so this guard never silently widens the set.
            continue
        granted |= set(role.permissions.permissions)
    requested = expand_implied(frozenset(granted))
    if actor_perms is None or not requested.issubset(actor_perms.permissions):
        raise CannotGrantPermissionsBeyondOwnSetError


@dataclass(slots=True, frozen=True)
class GrantSpec:
    role_id: RoleID
    scope_type: ScopeType
    scope_id: UUID | None


class GrantSpecResolver:
    """Validates :class:`GrantSpec` lists against the target product.

    Raises :class:`EntityNotFoundError` for a missing role or for a
    module/lesson scope id that does not exist or belongs to a
    different product. Raises :class:`InvalidScopeError` when a role
    from a different product is referenced.
    """

    def __init__(
        self,
        role_gateway: RoleGateway,
        lineage: ResourceLineageReader,
    ) -> None:
        self._role_gateway: Final = role_gateway
        self._lineage: Final = lineage

    async def resolve(
        self,
        product_id: ProductID,
        specs: list[GrantSpec],
    ) -> list[CollaborationGrant]:
        grants: list[CollaborationGrant] = []
        for spec in specs:
            await self._validate_role(product_id, spec.role_id)
            await self._validate_scope(
                product_id,
                spec.scope_type,
                spec.scope_id,
            )
            grants.append(
                CollaborationGrant.create(
                    role_id=spec.role_id,
                    scope_type=spec.scope_type,
                    scope_id=spec.scope_id,
                ),
            )
        return grants

    async def _validate_role(
        self,
        product_id: ProductID,
        role_id: RoleID,
    ) -> None:
        role = await self._role_gateway.with_id(role_id)
        if role is None:
            raise EntityNotFoundError(role_id)
        if role.product_id != product_id:
            raise InvalidScopeError("role_from_other_product")

    async def _validate_scope(
        self,
        product_id: ProductID,
        scope_type: ScopeType,
        scope_id: UUID | None,
    ) -> None:
        if scope_type is ScopeType.PRODUCT:
            return
        if scope_id is None:
            # Caught by ``CollaborationGrant.__post_init__`` later,
            # but raise here for a clearer error path.
            raise InvalidScopeError("missing_scope_id")
        if scope_type is ScopeType.MODULE:
            lineage = await self._lineage.lineage_for_module(scope_id)
            if lineage is None:
                raise EntityNotFoundError(scope_id)
            if lineage.product_id != product_id:
                raise InvalidScopeError("scope_in_other_product")
            return
        # LESSON
        lesson = await self._lineage.lineage_for_lesson(scope_id)
        if lesson is None:
            raise EntityNotFoundError(scope_id)
        if lesson.product_id != product_id:
            raise InvalidScopeError("scope_in_other_product")
