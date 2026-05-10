from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.product.ids import ProductID
from learnic.entities.role.ids import RoleID
from learnic.entities.role.models import Role
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RoleView:
    """Read-side projection of a :class:`Role`."""

    oid: RoleID
    product_id: ProductID
    name: str
    description: str | None
    position: int
    permissions: frozenset[Permission]
    created_by: UserID | None
    created_at: datetime
    updated_at: datetime


class RoleGateway(Protocol):
    """Write-side lookups for :class:`Role`."""

    async def with_id(self, oid: RoleID) -> Role | None: ...

    async def with_name_for_product(
        self,
        product_id: ProductID,
        name: str,
    ) -> Role | None:
        """Return the role with ``name`` inside ``product_id``, if any.

        Used by ``CreateCustomRole`` / ``UpdateCustomRole`` handlers
        to enforce the per-product unique-name invariant before
        attempting a write that would otherwise hit a DB constraint.
        """
        ...

    async def is_in_use(self, oid: RoleID) -> bool:
        """Return ``True`` if any collaboration grant references ``oid``.

        ``DeleteCustomRole`` calls this to honour the project's
        ``ON DELETE RESTRICT`` policy: deletion is blocked while at
        least one grant points at the role; the user must reassign
        affected collaborators first.
        """
        ...

    async def delete(self, role: Role) -> None: ...


class RoleSaver(Protocol):
    """Write-side persistence for :class:`Role`'s composite shape.

    A role's :attr:`Role.permissions` set lives in a child table —
    ``EntitySaver.add_one(role)`` only inserts the parent row.
    Handlers call :meth:`save` after staging the role to flush the
    parent + child rows in one logical operation; on update they
    call :meth:`replace_permissions` to swap the permission set
    atomically.
    """

    async def save(self, role: Role) -> None:
        """Persist a freshly created role with its permissions.

        Implementations may flush the parent row first to satisfy
        the ``role_permissions.role_id`` FK before writing the
        permission rows.
        """
        ...

    async def replace_permissions(self, role: Role) -> None:
        """Replace the persisted permission set with ``role.permissions``.

        Used by ``UpdateCustomRoleCommandHandler`` after mutating
        the in-memory aggregate. Idempotent w.r.t. reordering.
        """
        ...


class RoleReader(Protocol):
    """Read-side queries returning :class:`RoleView` projections."""

    async def with_id(self, oid: RoleID) -> RoleView | None: ...

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[RoleView]:
        """Return all roles defined inside ``product_id``.

        Ordered by ``position`` ascending (highest-rank first), then
        by ``created_at`` to break ties deterministically.
        """
        ...

    async def max_position_in_product(
        self,
        product_id: ProductID,
    ) -> int:
        """Return the largest ``position`` currently used in ``product_id``.

        Used by ``CreateCustomRoleCommand`` to slot a fresh role at
        the bottom of the hierarchy. Returns ``0`` when the product
        has no roles yet — the first role created via the Team-tab
        onboarding flow gets position ``10``.
        """
        ...

    async def min_position_for_user(
        self,
        product_id: ProductID,
        user_id: UserID,
    ) -> int | None:
        """Return the user's highest-rank role position on ``product_id``.

        Walks the user's active collaboration grants on the product
        scope and returns ``min(position)`` over the joined roles.
        Returns ``None`` when the user has no active grant on the
        product (i.e. is not on the team). Owner check is done
        separately by the caller — the owner row is not stored in
        ``product_collaborations``.
        """
        ...
