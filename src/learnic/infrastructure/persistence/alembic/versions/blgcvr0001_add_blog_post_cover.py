"""add blog post cover file

Adds the optional ``cover_file_id`` column to ``blog_posts`` — the
post's cover image shown on the public blog index and post cards.
Mirrors ``products.cover_file_id``: a nullable FK to the shared
``files`` table, ``ON DELETE SET NULL`` so the post survives its
cover file being purged.

Revision ID: blgcvr0001
Revises: note0001
Create Date: 2026-06-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "blgcvr0001"
down_revision: Union[str, Sequence[str], None] = "note0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "blog_posts",
        sa.Column("cover_file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_blog_posts_cover_file_id",
        "blog_posts",
        "files",
        ["cover_file_id"],
        ["oid"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_blog_posts_cover_file_id",
        "blog_posts",
        type_="foreignkey",
    )
    op.drop_column("blog_posts", "cover_file_id")
