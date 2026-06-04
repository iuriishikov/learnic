import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.blog_post.ids import BlogPostID
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.entities.blog_post_block.ids import BlogPostBlockID
from learnic.entities.blog_post_block.value_objects import (
    BlogBlockCaption,
    BlogHtmlContent,
)
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID


@dataclass
class BlogHtmlBlock(BaseEntity[BlogPostBlockID]):
    """An HTML-content block inside a blog post.

    ``html`` is sanitized server-side (in the command handler) before
    being wrapped in :class:`BlogHtmlContent`. ``position`` is the
    block's 0-based order within the post.
    """

    post_id: BlogPostID
    html: BlogHtmlContent
    position: int
    created_at: datetime
    updated_at: datetime

    @property
    def type(self) -> BlogPostBlockType:
        return BlogPostBlockType.HTML

    def update_html(self, new_html: BlogHtmlContent) -> None:
        self.html = new_html

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        post_id: BlogPostID,
        html: BlogHtmlContent,
        position: int,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=BlogPostBlockID(uuid.uuid4()),
            post_id=post_id,
            html=html,
            position=position,
            created_at=now,
            updated_at=now,
        )


@dataclass
class BlogImageBlock(BaseEntity[BlogPostBlockID]):
    """An uploaded-image block inside a blog post.

    Carries a single ``file_id`` pointing at the ``files`` table —
    the bytes live in S3. The "this file is actually an image"
    invariant (content-type prefix ``image/``) is enforced by the
    command handler at construction time, not at the VO/entity layer.
    ``caption`` is an optional short label shown beside the image.
    """

    post_id: BlogPostID
    file_id: FileID
    position: int
    created_at: datetime
    updated_at: datetime
    caption: BlogBlockCaption | None = None

    @property
    def type(self) -> BlogPostBlockType:
        return BlogPostBlockType.IMAGE

    def update_file(self, new_file_id: FileID) -> None:
        self.file_id = new_file_id

    def update_caption(self, new_caption: BlogBlockCaption | None) -> None:
        self.caption = new_caption

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        post_id: BlogPostID,
        file_id: FileID,
        position: int,
        caption: BlogBlockCaption | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=BlogPostBlockID(uuid.uuid4()),
            post_id=post_id,
            file_id=file_id,
            position=position,
            created_at=now,
            updated_at=now,
            caption=caption,
        )


@dataclass
class BlogVideoBlock(BaseEntity[BlogPostBlockID]):
    """An uploaded-video block inside a blog post.

    Sibling of :class:`BlogImageBlock` — same file-backed mechanics,
    different content-type contract (``video/`` prefix, enforced in
    the command handler). ``title`` is an optional short label shown
    beside the player.
    """

    post_id: BlogPostID
    file_id: FileID
    position: int
    created_at: datetime
    updated_at: datetime
    title: BlogBlockCaption | None = None

    @property
    def type(self) -> BlogPostBlockType:
        return BlogPostBlockType.VIDEO

    def update_file(self, new_file_id: FileID) -> None:
        self.file_id = new_file_id

    def update_title(self, new_title: BlogBlockCaption | None) -> None:
        self.title = new_title

    def change_position(self, new_position: int) -> None:
        self.position = new_position

    @classmethod
    def create(
        cls,
        post_id: BlogPostID,
        file_id: FileID,
        position: int,
        title: BlogBlockCaption | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=BlogPostBlockID(uuid.uuid4()),
            post_id=post_id,
            file_id=file_id,
            position=position,
            created_at=now,
            updated_at=now,
            title=title,
        )


BlogPostBlock = BlogHtmlBlock | BlogImageBlock | BlogVideoBlock
