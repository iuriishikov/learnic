import pytest

from learnic.entities.role.constants import (
    ROLE_DESCRIPTION_MAX_LEN,
    ROLE_NAME_MAX_LEN,
)
from learnic.entities.role.errors import (
    EmptyPermissionSetError,
    EmptyRoleFieldError,
    RoleFieldTooLongError,
)
from learnic.entities.role.permissions import Permission
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleDescription,
    RoleName,
)


class TestRoleName:
    def test_accepts_valid(self) -> None:
        assert RoleName("Editor").value == "Editor"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyRoleFieldError):
            RoleName("   ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(RoleFieldTooLongError):
            RoleName("x" * (ROLE_NAME_MAX_LEN + 1))


class TestRoleDescription:
    def test_accepts_valid(self) -> None:
        assert RoleDescription("Some role").value == "Some role"

    def test_rejects_blank(self) -> None:
        with pytest.raises(EmptyRoleFieldError):
            RoleDescription("  ")

    def test_rejects_too_long(self) -> None:
        with pytest.raises(RoleFieldTooLongError):
            RoleDescription("x" * (ROLE_DESCRIPTION_MAX_LEN + 1))


class TestPermissionSet:
    def test_rejects_empty(self) -> None:
        with pytest.raises(EmptyPermissionSetError):
            PermissionSet(frozenset())

    def test_includes_returns_membership(self) -> None:
        ps = PermissionSet.of(Permission.READ_PRODUCT)
        assert ps.includes(Permission.READ_PRODUCT)
        assert not ps.includes(Permission.PUBLISH)
        assert Permission.READ_PRODUCT in ps

    def test_with_added_returns_new_set(self) -> None:
        ps = PermissionSet.of(Permission.READ_PRODUCT)
        new = ps.with_added(Permission.PUBLISH)
        assert Permission.PUBLISH in new
        assert Permission.PUBLISH not in ps

    def test_with_removed_keeps_invariant(self) -> None:
        ps = PermissionSet.of(
            Permission.READ_PRODUCT,
            Permission.PUBLISH,
        )
        new = ps.with_removed(Permission.PUBLISH)
        assert Permission.PUBLISH not in new
        assert Permission.READ_PRODUCT in new

    def test_with_removed_to_empty_raises(self) -> None:
        ps = PermissionSet.of(Permission.READ_PRODUCT)
        with pytest.raises(EmptyPermissionSetError):
            ps.with_removed(Permission.READ_PRODUCT)

    def test_union_combines_permissions(self) -> None:
        a = PermissionSet.of(Permission.READ_PRODUCT)
        b = PermissionSet.of(Permission.PUBLISH)
        union = a.union(b)
        assert Permission.READ_PRODUCT in union
        assert Permission.PUBLISH in union
