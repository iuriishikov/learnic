from learnic.entities.common.errors import FieldError


class EmptyProductFieldError(FieldError):
    """Raised when a required string-like product field is empty."""

    field: str


class ProductFieldTooLongError(FieldError):
    """Raised when a string-like product field exceeds its max length."""

    field: str
    limit: int


class ProductDurationOutOfRangeError(FieldError):
    """Raised when total duration is outside the allowed range."""

    field: str
    minimum: int
    maximum: int


class InvalidWebinarLessonsError(FieldError):
    """Raised when total lessons count is outside the allowed range."""

    minimum: int
    maximum: int


class InvalidParticipantsLimitError(FieldError):
    """Raised when participants limit is below the allowed minimum."""

    minimum: int


class InvalidWebinarDurationError(FieldError):
    """Raised when default session duration is outside the allowed range."""

    minimum: int
    maximum: int


class InvalidAccessWindowError(FieldError):
    """Raised when access window is outside the allowed range."""

    minimum: int
    maximum: int


class InvalidStreamUrlError(FieldError):
    """Raised when ``StreamUrl`` invariants are violated.

    ``reason`` is one of ``"empty"``, ``"too_long"``,
    ``"invalid_scheme"``.
    """

    reason: str
