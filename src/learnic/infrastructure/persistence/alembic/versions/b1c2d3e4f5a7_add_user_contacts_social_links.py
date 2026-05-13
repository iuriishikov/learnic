"""add public contact fields + user_social_links table

Adds three optional contact columns to ``users``
(``website_url``, ``portfolio_url``, ``public_email``) and the
``user_social_links`` child table that backs the user's public
list of social-network links (one row per link, ordered by
``position``).

Revision ID: b1c2d3e4f5a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-11 16:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b1c2d3e4f5a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("website_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("portfolio_url", sa.String(length=2048), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("public_email", sa.String(length=320), nullable=True),
    )

    op.create_table(
        "user_social_links",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "linkedin",
                "twitter",
                "github",
                "telegram",
                "instagram",
                "youtube",
                "facebook",
                "tiktok",
                "vk",
                "dribbble",
                "behance",
                "other",
                name="social_link_kind",
            ),
            nullable=False,
        ),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    op.create_index(
        "ix_user_social_links_user_id_position",
        "user_social_links",
        ["user_id", "position"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_user_social_links_user_id_position",
        table_name="user_social_links",
    )
    op.drop_table("user_social_links")
    op.execute("DROP TYPE social_link_kind")
    op.drop_column("users", "public_email")
    op.drop_column("users", "portfolio_url")
    op.drop_column("users", "website_url")
