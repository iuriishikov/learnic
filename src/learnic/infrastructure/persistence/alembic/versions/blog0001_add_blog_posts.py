"""add blog posts and blog-post blocks (image / html / video)

Introduces an admin-authored blog: a ``blog_posts`` aggregate root
plus joined-inheritance block tables mirroring the lesson-block
design — a ``blog_post_blocks`` parent and one child table per type
(``blog_post_html_blocks``, ``blog_post_image_blocks``,
``blog_post_video_blocks``). Image and video blocks reference the
shared ``files`` table (bytes in S3); the ``image/`` vs ``video/``
content-type contract is enforced in the application layer, so the
columns are identical at the DB level.

Column widths are inlined (not imported from app constants) so the
migration is a self-contained snapshot of the schema at this revision.

Revision ID: blog0001
Revises: emlsnd0001
Create Date: 2026-05-29 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "blog0001"
down_revision: Union[str, Sequence[str], None] = "emlsnd0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TITLE_MAX_LEN = 200
_SLUG_MAX_LEN = 200
_HTML_MAX_LEN = 50_000
_CAPTION_MAX_LEN = 280


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "blog_posts",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=_TITLE_MAX_LEN), nullable=False),
        sa.Column("slug", sa.String(length=_SLUG_MAX_LEN), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "published", name="blog_post_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint("slug", name="uq_blog_posts_slug"),
    )
    op.create_index(
        "ix_blog_posts_status_created_at",
        "blog_posts",
        ["status", "created_at"],
    )

    op.create_table(
        "blog_post_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("image", "html", "video", name="blog_post_block_type"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["blog_posts.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_blog_post_blocks_post_position",
        "blog_post_blocks",
        ["post_id", "position"],
    )

    op.create_table(
        "blog_post_html_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("html", sa.String(length=_HTML_MAX_LEN), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["blog_post_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "blog_post_image_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column(
            "caption",
            sa.String(length=_CAPTION_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["blog_post_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "blog_post_video_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column(
            "title",
            sa.String(length=_CAPTION_MAX_LEN),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["blog_post_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["file_id"],
            ["files.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("blog_post_video_blocks")
    op.drop_table("blog_post_image_blocks")
    op.drop_table("blog_post_html_blocks")
    op.drop_index(
        "ix_blog_post_blocks_post_position",
        table_name="blog_post_blocks",
    )
    op.drop_table("blog_post_blocks")
    op.drop_index(
        "ix_blog_posts_status_created_at",
        table_name="blog_posts",
    )
    op.drop_table("blog_posts")
    op.execute("DROP TYPE blog_post_block_type")
    op.execute("DROP TYPE blog_post_status")
