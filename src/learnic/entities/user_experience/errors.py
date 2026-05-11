from learnic.entities.common.errors import FieldError


class EmptyUserExperienceFieldError(FieldError):
    """Raised when a required string field on a user experience is empty."""

    field: str


class UserExperienceFieldTooLongError(FieldError):
    """Raised when a string field on a user experience exceeds its limit."""

    field: str
    limit: int


class InvalidExperienceSourceUrlError(FieldError):
    """Raised when ``ExperienceSourceUrl`` invariants are violated.

    ``reason`` is one of ``"empty"``, ``"too_long"``,
    ``"invalid_scheme"``.
    """

    reason: str


class InvalidExperienceDateRangeError(FieldError):
    """Raised when ``end_date`` precedes ``start_date``.

    The aggregate enforces ``end_date >= start_date`` whenever both
    values are present; a ``None`` ``end_date`` means the experience
    is ongoing and is always accepted.
    """
