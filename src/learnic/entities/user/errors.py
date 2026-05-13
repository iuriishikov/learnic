from learnic.entities.common.errors import FieldError


class EmptyNameError(FieldError):
    field: str


class NameTooLongError(FieldError):
    field: str
    limit: int


class InvalidEmailError(FieldError):
    """Raised when an email string fails the VO's minimal invariants."""


class WeakPasswordError(FieldError):
    """Raised when a raw password violates length invariants.

    ``reason`` is one of ``"too_short"`` or ``"too_long"`` so that
    exception handlers can render a specific message without leaking
    the exact limit to the client.
    """

    reason: str


class InvalidDescriptionError(FieldError):
    """Raised when a user description is empty or exceeds the length limit."""

    limit: int


class InvalidContactUrlError(FieldError):
    """Raised when ``WebsiteUrl`` / ``PortfolioUrl`` invariants are violated.

    ``field`` distinguishes which contact URL was rejected (``website``
    or ``portfolio``); ``reason`` is one of ``"empty"``, ``"too_long"``
    or ``"invalid_scheme"``.
    """

    field: str
    reason: str


class InvalidPublicEmailError(FieldError):
    """Raised when the publicly-visible contact email VO is malformed."""


class TooManySocialLinksError(FieldError):
    """Raised when more social links are supplied than the configured cap."""

    limit: int


class InvalidSocialLinkUrlError(FieldError):
    """Raised when a social-link URL fails the URL invariants.

    ``reason`` is one of ``"empty"``, ``"too_long"`` or ``"invalid_scheme"``.
    """

    reason: str
