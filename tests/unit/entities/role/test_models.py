import uuid

from learnic.entities.product.ids import ProductID
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
    def test_assigns_metadata(self) -> None:
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


class TestRoleMutators:
    def test_role_can_be_renamed(self) -> None:
        role = Role.create_custom(
            product_id=_product_id(),
            name=RoleName("Lead Editor"),
            permissions=PermissionSet.of(Permission.READ_PRODUCT),
            position=RolePosition(1030),
            created_by=_user_id(),
        )
        role.rename(RoleName("Module Editor"))
        assert role.name == RoleName("Module Editor")

    def test_role_description_can_be_cleared(self) -> None:
        role = Role.create_custom(
            product_id=_product_id(),
            name=RoleName("Lead Editor"),
            permissions=PermissionSet.of(Permission.READ_PRODUCT),
            position=RolePosition(1040),
            created_by=_user_id(),
            description=RoleDescription("Owns module structure."),
        )
        role.update_description(None)
        assert role.description is None

    def test_role_permissions_can_be_replaced(self) -> None:
        role = Role.create_custom(
            product_id=_product_id(),
            name=RoleName("Lead Editor"),
            permissions=PermissionSet.of(Permission.READ_PRODUCT),
            position=RolePosition(1050),
            created_by=_user_id(),
        )
        role.update_permissions(
            PermissionSet.of(Permission.READ_PRODUCT, Permission.PUBLISH),
        )
        assert role.permissions is not None
        assert Permission.PUBLISH in role.permissions
