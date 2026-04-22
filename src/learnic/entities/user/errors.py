from learnic.entities.common.errors import FieldError


class EmptyNameError(FieldError):
    field: str


class NameTooLongError(FieldError):
    field: str
    limit: int


class InvalidEmailError(FieldError):
    """Raised when an email string fails the VO's minimal invariants."""


class WeakPasswordError(FieldError):
    """Raised when a raw password violates length invariants.

    ``reason`` is one of ``"too_short"`` or ``"too_long"`` so that
    exception handlers can render a specific message without leaking
    the exact limit to the client.
    """

    reason: str
