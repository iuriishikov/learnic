from learnic.entities.common.errors import FieldError


class EmptyTagFieldError(FieldError):
    """Raised when a required string-like tag field is empty."""

    field: str


class TagFieldTooLongError(FieldError):
    """Raised when a string-like tag field exceeds its max length."""

    field: str
    limit: int


class TooManyTagsError(FieldError):
    """Raised when an attempt would attach more than the per-product cap.

    The cap lives in :data:`learnic.entities.tag.constants.PRODUCT_TAGS_MAX`
    and is shared with the HTTP boundary so the SPA can reject before
    a round-trip.
    """

    limit: int
