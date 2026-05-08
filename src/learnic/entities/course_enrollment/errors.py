from learnic.entities.common.errors import FieldError


class InvalidProgressPercentError(FieldError):
    """Raised when ``ProgressPercent`` is outside the allowed range."""

    minimum: int
    maximum: int
