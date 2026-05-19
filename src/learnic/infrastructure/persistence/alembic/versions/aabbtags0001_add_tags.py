"""add tags + product_tags tables (global tag pool with product associations)

Tags are global, append-only, lookup by ``slug`` (lower-cased,
whitespace-collapsed ``name``). ``product_tags`` is the M2M
junction; the per-product list is rewritten in full by
``PUT /products/{product_id}/tags`` and ordered by ``position``.

Revision ID: aabbtags0001
Revises: ab01merge0000
Create Date: 2026-05-17 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "aabbtags0001"
down_revision: Union[str, Sequence[str], None] = "ab01merge0000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tags",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("slug", sa.String(length=30), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"])

    op.create_table(
        "product_tags",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("product_id", "tag_id"),
    )
    op.create_index(
        "ix_product_tags_tag_id",
        "product_tags",
        ["tag_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_product_tags_tag_id", table_name="product_tags")
    op.drop_table("product_tags")
    op.drop_index("ix_tags_slug", table_name="tags")
    op.drop_table("tags")
