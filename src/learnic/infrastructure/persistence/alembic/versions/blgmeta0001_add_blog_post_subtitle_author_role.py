"""add blog post subtitle and topic

Adds two optional editorial columns to ``blog_posts``:

* ``subtitle`` — short description / deck shown under the title on the
  public post page.
* ``topic`` — category label ("Design") shown above the title.

Both are nullable plain text, capped at ``BLOG_POST_SUBTITLE_MAX_LEN`` /
``BLOG_POST_TOPIC_MAX_LEN``.

Revision ID: blgmeta0001
Revises: blgcvr0001
Create Date: 2026-06-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from learnic.entities.blog_post.constants import (
    BLOG_POST_SUBTITLE_MAX_LEN,
    BLOG_POST_TOPIC_MAX_LEN,
)

revision: str = "blgmeta0001"
down_revision: Union[str, Sequence[str], None] = "blgcvr0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "blog_posts",
        sa.Column(
            "subtitle",
            sa.String(BLOG_POST_SUBTITLE_MAX_LEN),
            nullable=True,
        ),
    )
    op.add_column(
        "blog_posts",
        sa.Column(
            "topic",
            sa.String(BLOG_POST_TOPIC_MAX_LEN),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("blog_posts", "topic")
    op.drop_column("blog_posts", "subtitle")
