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


class OperationNotAllowedInStatusError(DomainError):
    """Raised when an operation is forbidden in the current status.

    Carries the offending ``status`` and ``operation`` so callers
    (the HTTP layer, logs, tests) can branch without parsing free
    text. Replaces the legacy per-operation error family
    (``CannotAcceptInThisStatusError`` / ``CannotDeclineInThisStatusError``
    / ``CannotRevokeInThisStatusError`` / ``CannotMutateInactiveCollaborationError``);
    the state-machine table in ``state_machine.py`` decides which
    operations apply in which status.
    """

    status: str
    operation: str


class InviteTokenMismatchError(DomainError):
    """Raised when the supplied accept-token does not match the stored hash."""


class InviteTokenExpiredError(DomainError):
    """Raised when the accept-token's TTL has elapsed."""
