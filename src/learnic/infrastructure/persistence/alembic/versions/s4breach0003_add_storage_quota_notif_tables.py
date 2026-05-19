"""add notification_storage_quota_{warning,enforced} subtype tables

Companion to the enum-extension migration ``s3breach0002`` —
creates the two subtype tables that hold the polymorphic bodies
for ``storage_quota_warning`` / ``storage_quota_enforced``
notifications. Each table has the standard composite FK back to
``notifications.(oid, kind)`` so a body row can only attach to a
parent row of the matching kind.

Revision ID: s4breach0003
Revises: s3breach0002
Create Date: 2026-05-20 10:10:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "s4breach0003"
down_revision: Union[str, Sequence[str], None] = "s3breach0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of ``PLAN_CODE_MAX_LEN``; see s1bill0001 for the rationale.
_PLAN_CODE_MAX_LEN = 32

_NOTIFICATION_KIND_ENUM = postgresql.ENUM(
    name="notification_kind",
    create_type=False,
)


def upgrade() -> None:
    """Create the two notification subtype tables."""
    op.create_table(
        "notification_storage_quota_warning",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _NOTIFICATION_KIND_ENUM, nullable=False),
        sa.Column(
            "plan_code",
            sa.String(_PLAN_CODE_MAX_LEN),
            nullable=False,
        ),
        sa.Column("over_bytes", sa.BigInteger(), nullable=False),
        sa.Column("plan_limit_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "grace_until",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_storage_quota_warning_parent",
        ),
        sa.CheckConstraint(
            "kind = 'storage_quota_warning'",
            name="ck_notif_storage_quota_warning_kind",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
    )
    op.create_table(
        "notification_storage_quota_enforced",
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("kind", _NOTIFICATION_KIND_ENUM, nullable=False),
        sa.Column(
            "plan_code",
            sa.String(_PLAN_CODE_MAX_LEN),
            nullable=False,
        ),
        sa.Column(
            "deleted_files_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column("freed_bytes", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id", "kind"],
            ["notifications.oid", "notifications.kind"],
            ondelete="CASCADE",
            name="fk_notif_storage_quota_enforced_parent",
        ),
        sa.CheckConstraint(
            "kind = 'storage_quota_enforced'",
            name="ck_notif_storage_quota_enforced_kind",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
    )


def downgrade() -> None:
    """Drop the subtype tables."""
    op.drop_table("notification_storage_quota_enforced")
    op.drop_table("notification_storage_quota_warning")
