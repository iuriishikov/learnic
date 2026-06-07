import re
from typing import ClassVar

from learnic.entities.blog_post.constants import (
    BLOG_POST_SLUG_MAX_LEN,
    BLOG_POST_SLUG_MIN_LEN,
    BLOG_POST_SUBTITLE_MAX_LEN,
    BLOG_POST_TITLE_MAX_LEN,
    BLOG_POST_TOPIC_MAX_LEN,
)
from learnic.entities.blog_post.errors import (
    BlogPostFieldTooLongError,
    EmptyBlogPostFieldError,
    InvalidBlogPostSlugError,
)
from learnic.entities.common.value_object import ValueObject


class BlogPostTitle(ValueObject):
    """Human-readable title of a blog post.

    Required and non-blank — a post always has a heading. Length is
    capped at ``BLOG_POST_TITLE_MAX_LEN``.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlogPostFieldError("title")
        if len(self.value) > BLOG_POST_TITLE_MAX_LEN:
            raise BlogPostFieldTooLongError("title", BLOG_POST_TITLE_MAX_LEN)


class BlogPostSlug(ValueObject):
    """URL-friendly identifier used in the public post path.

    Canonical form is lowercase alphanumerics joined by single
    hyphens (``my-first-post``) — no leading/trailing/double hyphens,
    no uppercase, no spaces. The value is stored verbatim; callers
    that want to derive a slug from a title must normalise it
    themselves before constructing the VO. Uniqueness across posts is
    a persistence-level concern (enforced by a unique index and a
    handler pre-check), not a VO invariant.
    """

    _PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise InvalidBlogPostSlugError("empty")
        if len(self.value) < BLOG_POST_SLUG_MIN_LEN:
            raise InvalidBlogPostSlugError("too_short")
        if len(self.value) > BLOG_POST_SLUG_MAX_LEN:
            raise BlogPostFieldTooLongError("slug", BLOG_POST_SLUG_MAX_LEN)
        if not self._PATTERN.match(self.value):
            raise InvalidBlogPostSlugError("invalid_format")


class BlogPostSubtitle(ValueObject):
    """Optional deck / standfirst shown under the title.

    Only constructed when a subtitle is actually present — the
    "no subtitle" case is the entity's ``None``, handled at the
    entity / persistence boundary, never an empty VO. Non-blank and
    capped at ``BLOG_POST_SUBTITLE_MAX_LEN``.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlogPostFieldError("subtitle")
        if len(self.value) > BLOG_POST_SUBTITLE_MAX_LEN:
            raise BlogPostFieldTooLongError(
                "subtitle",
                BLOG_POST_SUBTITLE_MAX_LEN,
            )


class BlogPostTopic(ValueObject):
    """Optional topic / category label ("Design") shown above the title.

    Only constructed when present (absent == entity ``None``); non-blank
    and capped at ``BLOG_POST_TOPIC_MAX_LEN``.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlogPostFieldError("topic")
        if len(self.value) > BLOG_POST_TOPIC_MAX_LEN:
            raise BlogPostFieldTooLongError(
                "topic",
                BLOG_POST_TOPIC_MAX_LEN,
            )
