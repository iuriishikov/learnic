from dataclasses import dataclass, field
from typing import Self

from learnic.entities.common.value_object import ValueObject
from learnic.entities.role.constants import (
    ROLE_DESCRIPTION_MAX_LEN,
    ROLE_NAME_MAX_LEN,
    ROLE_NAME_MIN_LEN,
    ROLE_POSITION_MAX,
    ROLE_POSITION_MIN,
)
from learnic.entities.role.errors import (
    EmptyPermissionSetError,
    EmptyRoleFieldError,
    InvalidRolePositionError,
    RoleFieldTooLongError,
)
from learnic.entities.role.permissions import Permission


class RoleName(ValueObject):
    value: str

    def __post_init__(self) -> None:
        stripped = self.value.strip()
        if len(stripped) < ROLE_NAME_MIN_LEN:
            raise EmptyRoleFieldError("name")
        if len(self.value) > ROLE_NAME_MAX_LEN:
            raise RoleFieldTooLongError("name", ROLE_NAME_MAX_LEN)


class RolePosition(ValueObject):
    """Discord-style hierarchy slot for a :class:`Role`.

    Lower value = higher rank. ``0`` is reserved for the synthetic
    owner position and never appears in storage; the smallest valid
    persisted value is ``ROLE_POSITION_MIN``. Comparison operators
    follow the natural integer order so callers can do
    ``actor.position < target.position`` directly.
    """

    value: int

    def __post_init__(self) -> None:
        if not (ROLE_POSITION_MIN <= self.value <= ROLE_POSITION_MAX):
            raise InvalidRolePositionError(
                "position",
                ROLE_POSITION_MAX,
            )

    def __lt__(self, other: "RolePosition") -> bool:
        return self.value < other.value

    def __le__(self, other: "RolePosition") -> bool:
        return self.value <= other.value


class RoleDescription(ValueObject):
    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyRoleFieldError("description")
        if len(self.value) > ROLE_DESCRIPTION_MAX_LEN:
            raise RoleFieldTooLongError(
                "description",
                ROLE_DESCRIPTION_MAX_LEN,
            )


@dataclass(slots=True, frozen=True, eq=True)
class PermissionSet:
    """Frozen, non-empty set of :class:`Permission` values.

    Defined as a regular dataclass (not via :class:`ValueObject`) so
    it can carry a non-trivial container field with a default factory
    and remain hashable. Composition with SQLAlchemy goes through a
    custom factory in the role mapper rather than ``__composite_values__``
    — permissions are stored in a child table, not a column.
    """

    permissions: frozenset[Permission] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if not self.permissions:
            raise EmptyPermissionSetError

    def __hash__(self) -> int:
        return hash(self.permissions)

    def __contains__(self, permission: Permission) -> bool:
        return permission in self.permissions

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.permissions)

    def __len__(self) -> int:
        return len(self.permissions)

    def includes(self, permission: Permission) -> bool:
        return permission in self.permissions

    def with_added(self, permission: Permission) -> Self:
        return type(self)(self.permissions | {permission})

    def with_removed(self, permission: Permission) -> Self:
        return type(self)(self.permissions - {permission})

    def union(self, other: "PermissionSet") -> Self:
        return type(self)(self.permissions | other.permissions)

    @classmethod
    def of(cls, *permissions: Permission) -> Self:
        return cls(frozenset(permissions))
