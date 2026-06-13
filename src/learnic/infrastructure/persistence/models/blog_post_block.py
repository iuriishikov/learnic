"""SA Core tables for blog-post blocks (joined inheritance, no mapper).

Blog blocks mirror the lesson-block design: a ``blog_post_blocks``
parent table plus one child table per block type
(``blog_post_html_blocks``, ``blog_post_image_blocks``,
``blog_post_video_blocks``). As with lesson blocks, the multi-table
INSERT/UPDATE semantics don't play nicely with imperative mapping, so
these tables are NOT mapped to entity classes — the gateway adapter
works via Core ``insert``/``update``/``select`` directly. This is the
same intentional, scoped exception used by ``note_block``.

Image and video blocks both reference the shared ``files`` table; the
``image/`` vs ``video/`` content-type contract is enforced upstream in
the command handler, not at the DB layer (the column is identical).
"""

from enum import StrEnum

import sqlalchemy as sa

from learnic.entities.blog_post_block.constants import (
    BLOG_BLOCK_CAPTION_MAX_LEN,
    BLOG_HTML_BLOCK_MAX_LEN,
)
from learnic.entities.blog_post_block.enums import BlogPostBlockType
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


blog_post_blocks_table = sa.Table(
    "blog_post_blocks",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "post_id",
        sa.Uuid,
        sa.ForeignKey("blog_posts.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "type",
        sa.Enum(
            BlogPostBlockType,
            name="blog_post_block_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column(
        "position",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    ),
    sa.Index(
        "ix_blog_post_blocks_post_position",
        "post_id",
        "position",
    ),
)


blog_post_html_blocks_table = sa.Table(
    "blog_post_html_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("blog_post_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "html",
        sa.String(BLOG_HTML_BLOCK_MAX_LEN),
        nullable=False,
    ),
)


blog_post_image_blocks_table = sa.Table(
    "blog_post_image_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("blog_post_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    # ``ON DELETE CASCADE`` + ``NOT NULL``: an image block always has a
    # backing file. Replace flows UPDATE the FK to the new file before
    # soft-deleting the old one, so a live block never points at a
    # purged file; when a file IS hard-deleted (by the purge worker),
    # the dependent block is cascaded away with it.
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "caption",
        sa.String(BLOG_BLOCK_CAPTION_MAX_LEN),
        nullable=True,
    ),
)


blog_post_video_blocks_table = sa.Table(
    "blog_post_video_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("blog_post_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "title",
        sa.String(BLOG_BLOCK_CAPTION_MAX_LEN),
        nullable=True,
    ),
)
