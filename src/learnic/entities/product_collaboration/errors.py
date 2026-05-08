from learnic.entities.common.errors import DomainError, FieldError


class InvalidInviteTokenError(FieldError):
    """Raised when an invite token violates length / charset invariants."""


class InvalidScopeError(FieldError):
    """Raised when a grant's scope is incompatible with its target.

    For example: ``ScopeType.PRODUCT`` requires ``scope_id is None``;
    ``ScopeType.MODULE`` and ``ScopeType.LESSON`` both require a
    non-null ``scope_id``.
    """

    reason: str


class EmptyGrantsError(FieldError):
    """Raised when an active collaboration has no grants.

    A collaboration without grants is functionally identical to a
    revoked one — disallow it explicitly so the invariant lives in
    the domain rather than scattered across handlers.
    """


class CannotAcceptInThisStatusError(DomainError):
    """Raised when ``accept()`` is called on a non-pending collaboration."""

    status: str


class CannotRevokeInThisStatusError(DomainError):
    """Raised when ``revoke()`` is called on an already-revoked collaboration."""


class CannotMutateInactiveCollaborationError(DomainError):
    """Raised when grants are updated on a non-active collaboration."""

    status: str


class InviteTokenMismatchError(DomainError):
    """Raised when the supplied accept-token does not match the stored hash."""


class InviteTokenExpiredError(DomainError):
    """Raised when the accept-token's TTL has elapsed."""
