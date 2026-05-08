from learnic.entities.common.errors import FieldError


class EmptyCohortFieldError(FieldError):
    """Raised when a required string-like cohort field is empty."""

    field: str


class CohortFieldTooLongError(FieldError):
    """Raised when a string-like cohort field exceeds its max length."""

    field: str
    limit: int


class InvalidIanaTimezoneError(FieldError):
    """Raised when ``IanaTimezone`` invariants are violated.

    ``reason`` is one of ``"empty"``, ``"too_long"``, ``"not_found"``.
    """

    reason: str


class InvalidRecurrenceRuleError(FieldError):
    """Raised when ``RecurrenceRule`` invariants are violated.

    ``reason`` is one of:
        * ``"empty"`` / ``"too_long"`` / ``"missing_freq"`` /
          ``"invalid_part"`` — raised by the value object's own
          format-level guard (stdlib only).
        * ``"semantic"`` — raised by an
          ``application``-layer ``RecurrenceRuleValidator`` when the
          rule is well-formed but cannot be parsed into a valid
          RFC 5545 sequence (e.g. ``BYDAY=ZZ`` or incompatible
          combinations).
    """

    reason: str


class InvalidRecordingUrlError(FieldError):
    """Raised when ``RecordingUrl`` invariants are violated.

    ``reason`` is one of ``"empty"``, ``"too_long"``,
    ``"invalid_scheme"``.
    """

    reason: str
