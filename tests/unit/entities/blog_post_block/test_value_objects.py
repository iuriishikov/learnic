import uuid

import pytest

from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.constants import (
    BLOG_BLOCK_CAPTION_MAX_LEN,
    BLOG_HTML_BLOCK_MAX_LEN,
)
from learnic.entities.blog_post_block.errors import (
    BlogBlockContentTooLongError,
    EmptyBlogBlockFieldError,
)
from learnic.entities.blog_post_block.models import (
    BlogHtmlBlock,
    BlogImageBlock,
    BlogVideoBlock,
)
from learnic.entities.blog_post_block.value_objects import (
    BlogBlockCaption,
    BlogHtmlContent,
)
from learnic.entities.file.ids import FileID


class TestBlogHtmlContent:
    def test_empty_allowed(self) -> None:
        # Authors create a block then fill it in the editor.
        assert BlogHtmlContent("").value == ""

    def test_too_long_rejected(self) -> None:
        with pytest.raises(BlogBlockContentTooLongError):
            BlogHtmlContent("x" * (BLOG_HTML_BLOCK_MAX_LEN + 1))


class TestBlogBlockCaption:
    def test_accepts_value(self) -> None:
        assert BlogBlockCaption("A caption").value == "A caption"

    @pytest.mark.parametrize("value", ["", "   "])
    def test_blank_rejected(self, value: str) -> None:
        with pytest.raises(EmptyBlogBlockFieldError):
            BlogBlockCaption(value)

    def test_too_long_rejected(self) -> None:
        with pytest.raises(BlogBlockContentTooLongError):
            BlogBlockCaption("x" * (BLOG_BLOCK_CAPTION_MAX_LEN + 1))


class TestBlockEntities:
    def test_html_block_type_and_mutators(self) -> None:
        post_id = BlogPostID(uuid.uuid4())
        block = BlogHtmlBlock.create(post_id, BlogHtmlContent("<p>x</p>"), 0)
        assert block.type.value == "html"
        block.update_html(BlogHtmlContent("<p>y</p>"))
        assert block.html.value == "<p>y</p>"
        block.change_position(3)
        assert block.position == 3

    def test_image_block_type_and_file_swap(self) -> None:
        post_id = BlogPostID(uuid.uuid4())
        block = BlogImageBlock.create(
            post_id, FileID(uuid.uuid4()), 0, BlogBlockCaption("cap"),
        )
        assert block.type.value == "image"
        new_file = FileID(uuid.uuid4())
        block.update_file(new_file)
        assert block.file_id == new_file
        block.update_caption(None)
        assert block.caption is None

    def test_video_block_type_and_title(self) -> None:
        post_id = BlogPostID(uuid.uuid4())
        block = BlogVideoBlock.create(post_id, FileID(uuid.uuid4()), 0)
        assert block.type.value == "video"
        assert block.title is None
        block.update_title(BlogBlockCaption("T"))
        assert block.title is not None
        assert block.title.value == "T"
