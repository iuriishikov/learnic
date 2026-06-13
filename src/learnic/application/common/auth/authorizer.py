from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission, ScopeType
from learnic.entities.role.value_objects import PermissionSet
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AuthzTarget:
    """The resource and scope being authorized against.

    ``target_type`` chooses the granularity at which the check is
    evaluated; ``target_id`` is the id of that resource (``None``
    only for ``ScopeType.PRODUCT``). For ``ScopeType.LESSON``
    targets ``module_id`` should also be set so module-scoped
    grants on the parent module can match.
    """

    product_id: ProductID
    target_type: ScopeType = ScopeType.PRODUCT
    target_id: UUID | None = None
    module_id: UUID | None = None

    @classmethod
    def for_product(cls, product_id: ProductID) -> "AuthzTarget":
        return cls(product_id=product_id)

    @classmethod
    def for_module(
        cls,
        product_id: ProductID,
        module_id: UUID,
    ) -> "AuthzTarget":
        return cls(
            product_id=product_id,
            target_type=ScopeType.MODULE,
            target_id=module_id,
            module_id=module_id,
        )

    @classmethod
    def for_lesson(
        cls,
        product_id: ProductID,
        module_id: UUID,
        lesson_id: UUID,
    ) -> "AuthzTarget":
        return cls(
            product_id=product_id,
            target_type=ScopeType.LESSON,
            target_id=lesson_id,
            module_id=module_id,
        )


class Authorizer(Protocol):
    """Permission resolver for product collaborators.

    Application command handlers call ``require(...)`` at the start
    of each ``run()`` to gate the operation behind a permission. The
    product author is short-circuited as having every permission;
    otherwise the implementation loads the caller's active
    collaboration, walks its grants against the target, expands
    permission implications via
    :func:`learnic.entities.role.permissions.expand_implied`, and
    raises :class:`InsufficientPermissionsError` when the requested
    permission is not in the resulting set.
    """

    async def require(
        self,
        actor: UserID,
        target: AuthzTarget,
        permission: Permission,
    ) -> None: ...

    async def require_owner(
        self,
        actor: UserID,
        product_id: ProductID,
    ) -> None:
        """Gate an operation to the product's author only.

        Unlike :meth:`require`, this bypasses the permission system
        entirely: it is satisfied **only** by the product's author,
        never by a collaborator — no role can grant it. Use it for
        operations that are intrinsically owner-only (e.g. switching
        a product between public and private visibility).

        Raises:
            NotResourceOwnerError: ``actor`` is not the author of
                ``product_id``; HTTP 403.
        """
        ...

    async def effective_permissions(
        self,
        actor: UserID,
        target: AuthzTarget,
    ) -> PermissionSet | None:
        """Return the resolved permissions for ``actor`` on ``target``.

        Returns ``None`` when the actor has no active collaboration
        and is not the product author. Returned set is the union of
        every covering grant's permissions, transitively expanded
        through :data:`PERMISSION_IMPLIES`.
        """
        ...

    async def manage_collaborators_for_products(
        self,
        actor: UserID,
        product_ids: set[ProductID],
    ) -> dict[ProductID, bool]:
        """Batch: does ``actor`` hold ``MANAGE_COLLABORATORS`` per product?

        Equivalent to calling :meth:`effective_permissions` once per
        product and testing for ``MANAGE_COLLABORATORS``, but resolved
        in a constant number of queries instead of O(N) — used by the
        notifications reader to hydrate the "can re-invite" flag on a
        cursor page without an N+1 against the authorizer. Every input
        id appears in the result; absent / unknown products map to
        ``False``.
        """
        ...
