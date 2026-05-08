"""add course content draft tables (modules + lessons)

Revision ID: d9e2f5a814c7
Revises: c4e7d2a98b51
Create Date: 2026-05-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9e2f5a814c7"
down_revision: Union[str, Sequence[str], None] = "c4e7d2a98b51"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "course_modules",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "description",
            sa.String(length=5000),
            nullable=True,
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
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_course_modules_product_position",
        "course_modules",
        ["product_id", "position"],
    )

    op.create_table(
        "course_lessons",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("module_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
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
            ["module_id"],
            ["course_modules.oid"],
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
        "ix_course_lessons_module_position",
        "course_lessons",
        ["module_id", "position"],
    )
    op.create_index(
        "ix_course_lessons_product_id",
        "course_lessons",
        ["product_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_course_lessons_product_id",
        table_name="course_lessons",
    )
    op.drop_index(
        "ix_course_lessons_module_position",
        table_name="course_lessons",
    )
    op.drop_table("course_lessons")

    op.drop_index(
        "ix_course_modules_product_position",
        table_name="course_modules",
    )
    op.drop_table("course_modules")
