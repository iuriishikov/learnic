"""add statistic tables

Adds the base ``statistics`` table plus a subtype table per
:class:`StatisticType` (profile_view, product_view). Same option
B persistence shape as ``notifications``: composite
``(statistic_id, type)`` foreign key + CHECK constraint pinning
the subtype to its type so a row of the wrong type cannot
attach.

The parent ``statistics`` row carries the actor (always
authenticated — the application layer enforces this; the column
is NOT NULL) plus ``type`` / ``created_at``. Each subtype table
holds the kind-specific columns (target user / product id) and
an optional truncated ``Referer`` header capped at
``REFERRER_MAX_LEN`` (512).

Indexes on the parent target the two access patterns we expect
first: list-by-actor (latest events for a user) and aggregate-
by-type (volume per event type). Per-subtype indexes target
"views of target X" lookups.

Revision ID: be01f2a3b4c5
Revises: b1c8d9e0f234
Create Date: 2026-05-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "be01f2a3b4c5"
down_revision: Union[str, Sequence[str], None] = "b1c8d9e0f234"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "statistics",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "profile_view",
                "product_view",
                name="statistic_type",
            ),
            nullable=False,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint(
            "oid",
            "type",
            name="uq_statistics_oid_type",
        ),
    )
    op.create_index(
        "ix_stat_actor_created",
        "statistics",
        ["actor_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_stat_type_created",
        "statistics",
        ["type", sa.text("created_at DESC")],
    )

    op.create_table(
        "statistic_profile_view",
        sa.Column("statistic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "profile_view",
                "product_view",
                name="statistic_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("target_user_id", sa.Uuid(), nullable=False),
        sa.Column("referrer", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["statistic_id", "type"],
            ["statistics.oid", "statistics.type"],
            ondelete="CASCADE",
            name="fk_stat_profile_view_parent",
        ),
        sa.ForeignKeyConstraint(
            ["target_user_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("statistic_id"),
        sa.CheckConstraint(
            "type = 'profile_view'",
            name="ck_stat_profile_view_type",
        ),
    )
    op.create_index(
        "ix_stat_profile_view_target",
        "statistic_profile_view",
        ["target_user_id"],
    )

    op.create_table(
        "statistic_product_view",
        sa.Column("statistic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            postgresql.ENUM(
                "profile_view",
                "product_view",
                name="statistic_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("referrer", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["statistic_id", "type"],
            ["statistics.oid", "statistics.type"],
            ondelete="CASCADE",
            name="fk_stat_product_view_parent",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("statistic_id"),
        sa.CheckConstraint(
            "type = 'product_view'",
            name="ck_stat_product_view_type",
        ),
    )
    op.create_index(
        "ix_stat_product_view_product",
        "statistic_product_view",
        ["product_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_stat_product_view_product",
        table_name="statistic_product_view",
    )
    op.drop_table("statistic_product_view")
    op.drop_index(
        "ix_stat_profile_view_target",
        table_name="statistic_profile_view",
    )
    op.drop_table("statistic_profile_view")
    op.drop_index("ix_stat_type_created", table_name="statistics")
    op.drop_index("ix_stat_actor_created", table_name="statistics")
    op.drop_table("statistics")
    op.execute("DROP TYPE statistic_type")
