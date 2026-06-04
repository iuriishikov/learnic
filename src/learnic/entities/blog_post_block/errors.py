from learnic.entities.common.errors import FieldError


class EmptyBlogBlockFieldError(FieldError):
    """Raised when a required string-like blog-block field is empty."""

    field: str


class BlogBlockContentTooLongError(FieldError):
    """Raised when a blog-block field exceeds its max length."""

    field: str
    limit: int
