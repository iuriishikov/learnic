import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
from learnic.entities.role.enums import RoleKind
from learnic.entities.role.errors import CannotMutateSystemRoleError
from learnic.entities.role.ids import RoleID
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleDescription,
    RoleName,
    RolePosition,
)
from learnic.entities.user.models import UserID


@dataclass
class Role(BaseEntity[RoleID]):
    """A named bundle of permissions referenced by collaboration grants.

    System roles (``kind=SYSTEM``) carry ``product_id=None`` and are
    seeded once via Alembic — they are visible to every product and
    cannot be mutated through the public API. Custom roles
    (``kind=CUSTOM``) belong to exactly one product and are managed
    by collaborators with ``MANAGE_ROLES``.

    The aggregate is intentionally thin — ``permissions`` is loaded
    out-of-band by the gateway from a child table, mirroring how
    ``Product`` loads ``webinar_details``. The class-level
    ``permissions = None`` default keeps it accessible right
    after SA hydrates the row; the gateway always populates it
    before returning, so business code can treat it as non-null.
    """

    product_id: ProductID | None
    kind: RoleKind
    name: RoleName
    description: RoleDescription | None
    position: RolePosition
    created_by: UserID | None
    created_at: datetime
    updated_at: datetime
    permissions: PermissionSet | None = None

    def rename(self, new_name: RoleName) -> None:
        self._guard_mutable()
        self.name = new_name

    def update_description(
        self,
        new_description: RoleDescription | None,
    ) -> None:
        self._guard_mutable()
        self.description = new_description

    def update_permissions(self, new_permissions: PermissionSet) -> None:
        self._guard_mutable()
        self.permissions = new_permissions

    def reposition(self, new_position: RolePosition) -> None:
        """Move the role to a new hierarchy slot.

        System-role positions are also movable per-product in the
        future; for now the entity allows it and the application
        layer chooses whether to expose the operation. The mutability
        guard is intentionally NOT applied here.
        """
        self.position = new_position

    def _guard_mutable(self) -> None:
        if self.kind is RoleKind.SYSTEM:
            raise CannotMutateSystemRoleError

    @classmethod
    def create_custom(
        cls,
        product_id: ProductID,
        name: RoleName,
        permissions: PermissionSet,
        position: RolePosition,
        created_by: UserID,
        description: RoleDescription | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=RoleID(uuid.uuid4()),
            product_id=product_id,
            kind=RoleKind.CUSTOM,
            name=name,
            description=description,
            position=position,
            permissions=permissions,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
