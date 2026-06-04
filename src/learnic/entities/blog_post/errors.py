from learnic.entities.common.errors import DomainError, FieldError


class EmptyBlogPostFieldError(FieldError):
    """Raised when a required string-like blog-post field is empty."""

    field: str


class BlogPostFieldTooLongError(FieldError):
    """Raised when a string-like blog-post field exceeds its max length."""

    field: str
    limit: int


class InvalidBlogPostSlugError(FieldError):
    """Raised when a slug can't be parsed as a URL-friendly identifier.

    ``reason`` is one of ``"empty"``, ``"too_short"`` or
    ``"invalid_format"`` (anything other than lowercase alphanumerics
    joined by single hyphens, e.g. ``my-first-post``).
    """

    reason: str


class BlogPostStatusTransitionError(DomainError):
    """Raised when a publish/unpublish transition is invalid.

    ``status`` is the post's current status and ``operation`` is the
    attempted transition (``"publish"`` / ``"unpublish"``). Publishing
    an already-published post or unpublishing a draft are the two
    cases this guards. Surfaces as HTTP 409 — the closed set of
    statuses means every invalid transition is enumerable, not a
    catch-all.
    """

    status: str
    operation: str
