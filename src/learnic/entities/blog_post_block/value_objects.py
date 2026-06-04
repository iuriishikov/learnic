from learnic.entities.blog_post_block.constants import (
    BLOG_BLOCK_CAPTION_MAX_LEN,
    BLOG_HTML_BLOCK_MAX_LEN,
)
from learnic.entities.blog_post_block.errors import (
    BlogBlockContentTooLongError,
    EmptyBlogBlockFieldError,
)
from learnic.entities.common.value_object import ValueObject


class BlogHtmlContent(ValueObject):
    """Sanitized HTML body of a blog HTML block.

    The VO enforces only the length invariant — sanitization is done
    in the command handler via the ``HtmlSanitizer`` Protocol BEFORE
    the VO is constructed, and length is measured after sanitization.
    Empty values are accepted: admins create a block first and fill
    the body in the editor afterwards.
    """

    value: str

    def __post_init__(self) -> None:
        if len(self.value) > BLOG_HTML_BLOCK_MAX_LEN:
            raise BlogBlockContentTooLongError("html", BLOG_HTML_BLOCK_MAX_LEN)


class BlogBlockCaption(ValueObject):
    """Optional caption / title for an image or video block.

    Shared across the two media block types — both expose the same
    "short label beside the asset" affordance (an image caption, a
    video title) with no type-specific invariant. Non-blank when
    present; clear the field by passing ``None`` rather than an empty
    string.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise EmptyBlogBlockFieldError("caption")
        if len(self.value) > BLOG_BLOCK_CAPTION_MAX_LEN:
            raise BlogBlockContentTooLongError(
                "caption",
                BLOG_BLOCK_CAPTION_MAX_LEN,
            )
