import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
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

    Every role belongs to exactly one product (``product_id``) and is
    managed by collaborators with ``MANAGE_ROLES`` (the product author
    always has every permission by short-circuit). The frontend
    bootstraps an initial role set via the Team-tab onboarding flow
    when a product has no roles yet — there is no shared system-role
    catalogue.

    The aggregate is intentionally thin — ``permissions`` is loaded
    out-of-band by the gateway from a child table, mirroring how
    ``Product`` loads ``webinar_details``. The class-level
    ``permissions = None`` default keeps it accessible right
    after SA hydrates the row; the gateway always populates it
    before returning, so business code can treat it as non-null.
    """

    product_id: ProductID
    name: RoleName
    description: RoleDescription | None
    position: RolePosition
    created_by: UserID | None
    created_at: datetime
    updated_at: datetime
    permissions: PermissionSet | None = None

    def rename(self, new_name: RoleName) -> None:
        self.name = new_name

    def update_description(
        self,
        new_description: RoleDescription | None,
    ) -> None:
        self.description = new_description

    def update_permissions(self, new_permissions: PermissionSet) -> None:
        self.permissions = new_permissions

    def reposition(self, new_position: RolePosition) -> None:
        self.position = new_position

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
            name=name,
            description=description,
            position=position,
            permissions=permissions,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
