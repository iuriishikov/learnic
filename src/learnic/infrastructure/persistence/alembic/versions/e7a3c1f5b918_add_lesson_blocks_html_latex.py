"""add lesson_blocks parent and html/latex child tables

Revision ID: e7a3c1f5b918
Revises: d9e2f5a814c7
Create Date: 2026-05-01 06:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7a3c1f5b918"
down_revision: Union[str, Sequence[str], None] = "d9e2f5a814c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lesson_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("html", "latex", name="lesson_block_type"),
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
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["course_lessons.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_lesson_blocks_lesson_position",
        "lesson_blocks",
        ["lesson_id", "position"],
    )
    op.create_index(
        "ix_lesson_blocks_product_id",
        "lesson_blocks",
        ["product_id"],
    )

    op.create_table(
        "html_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("html", sa.String(length=50000), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "latex_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=50000), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("latex_blocks")
    op.drop_table("html_blocks")
    op.drop_index(
        "ix_lesson_blocks_product_id",
        table_name="lesson_blocks",
    )
    op.drop_index(
        "ix_lesson_blocks_lesson_position",
        table_name="lesson_blocks",
    )
    op.drop_table("lesson_blocks")
    op.execute("DROP TYPE lesson_block_type")
