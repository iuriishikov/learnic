from learnic.entities.common.errors import DomainError, FieldError


class InvalidProgressPercentError(FieldError):
    """Raised when :class:`ProgressPercent` is outside its allowed range."""

    minimum: int
    maximum: int


class EnrollmentDoesNotSupportError(DomainError):
    """Raised when an enrollment type lacks a requested capability.

    Mirrors :class:`ProductDoesNotSupportError`: a single error that
    carries the offending enrollment, its type, and the capability
    the operation needed, so the SPA can produce a useful message
    without sprinkling ``if enrollment.type is not …`` across
    handlers.
    """

    enrollment_id: object
    enrollment_type: str
    capability: str
