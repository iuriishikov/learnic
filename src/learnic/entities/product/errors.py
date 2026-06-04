from learnic.entities.common.errors import DomainError, FieldError


class ProductDoesNotSupportError(DomainError):
    """Raised when a product type does not support the requested capability.

    Replaces the legacy ``NotANoteError`` / ``NotAWebinarError``
    pair with a single error that carries enough context for the
    SPA to localise a useful message — the offending product, its
    type, and the capability the operation needed.
    """

    product_id: object
    product_type: str
    capability: str


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


