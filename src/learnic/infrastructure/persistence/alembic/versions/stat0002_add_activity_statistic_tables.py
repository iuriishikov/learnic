"""add registration / enrollment / site_visit statistic subtype tables

Creates one ``statistic_<type>`` subtype table per activity kind added
in ``stat0001``, following the same composite ``(statistic_id, type)``
FK + CHECK pattern as the existing view subtype tables. Registration
and site-visit carry no kind-specific columns — the parent row's
actor + ``created_at`` are the whole signal (registrations-over-time,
DAU / MAU). Enrollment additionally pins ``product_id`` so enrollments
can be broken down per course.

Revision ID: stat0002
Revises: stat0001
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "stat0002"
down_revision: Union[str, Sequence[str], None] = "stat0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATISTIC_TYPE = postgresql.ENUM(
    "profile_view",
    "product_view",
    "registration",
    "enrollment",
    "site_visit",
    name="statistic_type",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "statistic_registration",
        sa.Column("statistic_id", sa.Uuid(), nullable=False),
        sa.Column("type", _STATISTIC_TYPE, nullable=False),
        sa.ForeignKeyConstraint(
            ["statistic_id", "type"],
            ["statistics.oid", "statistics.type"],
            ondelete="CASCADE",
            name="fk_stat_registration_parent",
        ),
        sa.PrimaryKeyConstraint("statistic_id"),
        sa.CheckConstraint(
            "type = 'registration'",
            name="ck_stat_registration_type",
        ),
    )

    op.create_table(
        "statistic_enrollment",
        sa.Column("statistic_id", sa.Uuid(), nullable=False),
        sa.Column("type", _STATISTIC_TYPE, nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["statistic_id", "type"],
            ["statistics.oid", "statistics.type"],
            ondelete="CASCADE",
            name="fk_stat_enrollment_parent",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("statistic_id"),
        sa.CheckConstraint(
            "type = 'enrollment'",
            name="ck_stat_enrollment_type",
        ),
    )
    op.create_index(
        "ix_stat_enrollment_product",
        "statistic_enrollment",
        ["product_id"],
    )

    op.create_table(
        "statistic_site_visit",
        sa.Column("statistic_id", sa.Uuid(), nullable=False),
        sa.Column("type", _STATISTIC_TYPE, nullable=False),
        sa.ForeignKeyConstraint(
            ["statistic_id", "type"],
            ["statistics.oid", "statistics.type"],
            ondelete="CASCADE",
            name="fk_stat_site_visit_parent",
        ),
        sa.PrimaryKeyConstraint("statistic_id"),
        sa.CheckConstraint(
            "type = 'site_visit'",
            name="ck_stat_site_visit_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("statistic_site_visit")
    op.drop_index(
        "ix_stat_enrollment_product",
        table_name="statistic_enrollment",
    )
    op.drop_table("statistic_enrollment")
    op.drop_table("statistic_registration")
