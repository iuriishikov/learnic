from learnic.entities.common.errors import DomainError, FieldError


class EmptyRoleFieldError(FieldError):
    """Raised when a required string-like role field is empty."""

    field: str


class RoleFieldTooLongError(FieldError):
    """Raised when a string-like role field exceeds its max length."""

    field: str
    limit: int


class EmptyPermissionSetError(FieldError):
    """Raised when a role is constructed with no permissions.

    A role with zero permissions is meaningless — the closest
    "no-access" semantics is no collaboration at all.
    """


class InvalidRolePositionError(FieldError):
    """Raised when a role position is outside the allowed range."""

    field: str
    limit: int


class RoleHierarchyViolationError(DomainError):
    """Raised when a caller tries to act on a role/user at or above their own rank.

    The application layer translates this to HTTP 403 — it is an
    authorisation failure (the caller is authenticated and even has
    ``MANAGE_COLLABORATORS``, but lacks rank), not a 422 input error.
    """


class CannotGrantPermissionsBeyondOwnSetError(DomainError):
    """Raised when a caller tries to mint or amend a custom role
    that contains permissions outside their own effective set.

    Closes the obvious privilege-escalation bypass: an Editor with
    ``MANAGE_ROLES`` (no ``MANAGE_COLLABORATORS``) creating a
    "Super Editor" role with ``MANAGE_COLLABORATORS`` and
    assigning it to themselves.
    """
