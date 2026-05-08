from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.role_hierarchy import RoleHierarchy
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMyEffectivePermissionsQuery:
    actor_id: UserID
    product_id: ProductID


@dataclass(slots=True, frozen=True)
class EffectivePermissionsView:
    """Caller's resolved access to a product.

    ``hierarchy_position`` mirrors the rank used by the backend to
    enforce assignment / target rules: ``0`` for the product owner,
    a positive integer for a collaborator (their highest-rank role),
    or ``None`` when the caller has no rank at all (no permissions
    either). The frontend uses it to filter assignable roles and
    hide management actions on members ranked at or above the caller.
    """

    permissions: tuple[Permission, ...]
    hierarchy_position: int | None


@final
class GetMyEffectivePermissionsQueryHandler:
    """Returns the caller's resolved permissions for a product.

    The frontend uses this to gate edit buttons, hide management
    sections, and decide whether to show the "leave" / "manage roles"
    UI. An empty list means "no access" — but the route should map
    this to 403 only if the caller is fully unauthorized; here the
    query itself returns whatever the resolver decides.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        hierarchy: RoleHierarchy,
    ) -> None:
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy

    async def run(
        self,
        data: GetMyEffectivePermissionsQuery,
    ) -> EffectivePermissionsView:
        permissions = await self._authorizer.effective_permissions(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
        )
        position = await self._hierarchy.actor_position(
            data.product_id,
            data.actor_id,
        )
        if permissions is None:
            return EffectivePermissionsView(
                permissions=(),
                hierarchy_position=position,
            )
        return EffectivePermissionsView(
            permissions=tuple(sorted(permissions.permissions, key=str)),
            hierarchy_position=position,
        )
