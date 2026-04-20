class DomainError(Exception):
    """Base class for all domain-layer errors."""


class FieldError(DomainError):
    """Raised when a value object invariant is violated."""
