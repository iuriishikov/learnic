"""add product tables

Revision ID: d2f8a91c4e6b
Revises: c8d4e6a19b52
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2f8a91c4e6b"
down_revision: Union[str, Sequence[str], None] = "c8d4e6a19b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "products",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("course", "webinar", name="product_type"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "published",
                "archived",
                "banned",
                name="product_status",
            ),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "total_duration_in_hours",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "price_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "price_currency",
            sa.Enum("USD", "EUR", "RUB", "KZT", "BYN", name="currency"),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=True,
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
            ["author_id"],
            ["users.oid"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_products_author_id",
        "products",
        ["author_id"],
    )
    op.create_index(
        "ix_products_type_status",
        "products",
        ["type", "status"],
    )

    op.create_table(
        "product_webinar_details",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("total_lessons", sa.Integer(), nullable=False),
        sa.Column(
            "default_duration_minutes",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "allow_recording",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "default_max_participants",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "default_stream_url",
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            "access_window_minutes",
            sa.Integer(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_id"),
    )

    op.create_table(
        "product_qa",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.String(length=500), nullable=False),
        sa.Column("answer", sa.String(length=5000), nullable=False),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_product_qa_product_id_position",
        "product_qa",
        ["product_id", "position"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_product_qa_product_id_position",
        table_name="product_qa",
    )
    op.drop_table("product_qa")

    op.drop_table("product_webinar_details")

    op.drop_index("ix_products_type_status", table_name="products")
    op.drop_index("ix_products_author_id", table_name="products")
    op.drop_table("products")

    op.execute("DROP TYPE currency")
    op.execute("DROP TYPE product_status")
    op.execute("DROP TYPE product_type")
