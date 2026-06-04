from learnic.entities.common.errors import DomainError, FieldError


class InvalidProgressPercentError(FieldError):
    """Raised when :class:`ProgressPercent` is outside its allowed range."""

    minimum: int
    maximum: int


class EnrollmentDoesNotSupportError(DomainError):
    """Raised when an enrollment kind lacks a requested capability.

    Mirrors :class:`ProductDoesNotSupportError`: a single error that
    carries the offending enrollment, its kind, and the capability
    the operation needed, so the SPA can produce a useful message
    without sprinkling ``if enrollment.kind is not …`` across
    handlers.
    """

    enrollment_id: object
    enrollment_kind: str
    capability: str


class CannotRepinRevokedEnrollmentError(DomainError):
    """Raised when re-pinning is attempted on a non-ACTIVE enrollment.

    Revoked enrollments have no access to note content, so
    moving them to a different release would either expose
    content the student no longer has access to, or be a silent
    no-op once they re-enroll. Authors must restore access first
    (a future un-revoke flow) before changing the pinned release.
    """

    enrollment_id: object
    status: str
