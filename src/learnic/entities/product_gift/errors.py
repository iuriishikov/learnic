from learnic.entities.common.errors import DomainError, FieldError


class InvalidInviteTokenError(FieldError):
    """Raised when a gift token violates length / charset invariants."""


class OperationNotAllowedInGiftStatusError(DomainError):
    """Raised when an operation is forbidden in the current gift status.

    Carries the offending ``status`` and ``operation`` so callers
    (the HTTP layer, logs, tests) can branch without parsing free
    text. The state-machine table in ``state_machine.py`` decides
    which operations apply in which status.
    """

    status: str
    operation: str


class InviteTokenMismatchError(DomainError):
    """Raised when the supplied accept-token does not match the stored hash."""


class InviteTokenExpiredError(DomainError):
    """Raised when the gift's accept-token TTL has elapsed."""
