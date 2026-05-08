import uuid

import pytest

from learnic.entities.product.ids import ProductID
from learnic.entities.role.enums import RoleKind
from learnic.entities.role.errors import CannotMutateSystemRoleError
from learnic.entities.role.models import Role
from learnic.entities.role.permissions import Permission
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleDescription,
    RoleName,
    RolePosition,
)
from learnic.entities.user.models import UserID


def _user_id() -> UserID:
    return UserID(uuid.uuid4())


def _product_id() -> ProductID:
    return ProductID(uuid.uuid4())


class TestRoleCreateCustom:
    def test_assigns_kind_and_metadata(self) -> None:
        product_id = _product_id()
        creator = _user_id()
        role = Role.create_custom(
            product_id=product_id,
            name=RoleName("Lead Editor"),
            permissions=PermissionSet.of(
                Permission.READ_PRODUCT,
                Permission.EDIT_MODULES,
            ),
            position=RolePosition(1010),
            created_by=creator,
            description=RoleDescription("Owns module structure."),
        )
        assert role.kind is RoleKind.CUSTOM
        assert role.product_id == product_id
        assert role.created_by == creator
        assert role.permissions is not None
        assert Permission.EDIT_MODULES in role.permissions

    def test_create_without_description(self) -> None:
        role = Role.create_custom(
            product_id=_product_id(),
            name=RoleName("Lead Editor"),
            permissions=PermissionSet.of(Permission.READ_PRODUCT),
            position=RolePosition(1020),
            created_by=_user_id(),
        )
        assert role.description is None


class TestRoleMutationGuards:
    def _make_system_role(self) -> Role:
        # Use the constructor directly to mimic the Alembic seed.
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        return Role(
            oid=uuid.uuid4(),  # type: ignore[arg-type]
            product_id=None,
            kind=RoleKind.SYSTEM,
            name=RoleName("Editor"),
            description=None,
            position=RolePosition(200),
            created_by=None,
            created_at=now,
            updated_at=now,
            permissions=PermissionSet.of(Permission.READ_PRODUCT),
        )

    def test_system_role_rejects_rename(self) -> None:
        role = self._make_system_role()
        with pytest.raises(CannotMutateSystemRoleError):
            role.rename(RoleName("Other"))

    def test_system_role_rejects_description_change(self) -> None:
        role = self._make_system_role()
        with pytest.raises(CannotMutateSystemRoleError):
            role.update_description(RoleDescription("x"))

    def test_system_role_rejects_permission_change(self) -> None:
        role = self._make_system_role()
        with pytest.raises(CannotMutateSystemRoleError):
            role.update_permissions(
                PermissionSet.of(Permission.PUBLISH),
            )

    def test_custom_role_can_be_renamed(self) -> None:
        role = Role.create_custom(
            product_id=_product_id(),
            name=RoleName("Lead Editor"),
            permissions=PermissionSet.of(Permission.READ_PRODUCT),
            position=RolePosition(1030),
            created_by=_user_id(),
        )
        role.rename(RoleName("Module Editor"))
        assert role.name == RoleName("Module Editor")
