import pytest

from learnic.entities.blog_post.constants import (
    BLOG_POST_SLUG_MAX_LEN,
    BLOG_POST_TITLE_MAX_LEN,
)
from learnic.entities.blog_post.errors import (
    BlogPostFieldTooLongError,
    EmptyBlogPostFieldError,
    InvalidBlogPostSlugError,
)
from learnic.entities.blog_post.value_objects import (
    BlogPostSlug,
    BlogPostTitle,
)


class TestBlogPostTitle:
    def test_accepts_normal_value(self) -> None:
        assert BlogPostTitle("Hello").value == "Hello"

    @pytest.mark.parametrize("value", ["", "   ", "\t\n"])
    def test_blank_rejected(self, value: str) -> None:
        with pytest.raises(EmptyBlogPostFieldError):
            BlogPostTitle(value)

    def test_too_long_rejected(self) -> None:
        with pytest.raises(BlogPostFieldTooLongError):
            BlogPostTitle("x" * (BLOG_POST_TITLE_MAX_LEN + 1))


class TestBlogPostSlug:
    @pytest.mark.parametrize(
        "value",
        ["my-first-post", "abc", "a1b2c3", "intro-to-async-python-3"],
    )
    def test_valid_slugs(self, value: str) -> None:
        assert BlogPostSlug(value).value == value

    @pytest.mark.parametrize(
        ("value", "reason"),
        [
            ("", "empty"),
            ("ab", "too_short"),
            ("-x", "too_short"),
            ("Hello-World", "invalid_format"),
            ("bad_slug", "invalid_format"),
            ("trailing-", "invalid_format"),
            ("double--hyphen", "invalid_format"),
            ("двач", "invalid_format"),
            ("with space", "invalid_format"),
        ],
    )
    def test_invalid_slugs(self, value: str, reason: str) -> None:
        with pytest.raises(InvalidBlogPostSlugError) as exc:
            BlogPostSlug(value)
        assert exc.value.reason == reason

    def test_too_long_rejected(self) -> None:
        with pytest.raises(BlogPostFieldTooLongError):
            BlogPostSlug("a" * (BLOG_POST_SLUG_MAX_LEN + 1))
