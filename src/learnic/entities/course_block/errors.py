from learnic.entities.common.errors import FieldError


class EmptyBlockContentError(FieldError):
    """Raised when a block's body is empty after construction."""

    field: str


class BlockContentTooLongError(FieldError):
    """Raised when a block's body exceeds its max length."""

    field: str
    limit: int


class InvalidRutubeUrlError(FieldError):
    """Raised when a string can't be parsed as a Rutube video URL.

    ``reason`` is one of ``"empty"``, ``"unsupported_host"``,
    ``"missing_id"``, ``"invalid_id_format"``.
    """

    reason: str
