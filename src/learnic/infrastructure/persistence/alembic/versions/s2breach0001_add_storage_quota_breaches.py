"""add storage_quota_breaches table

Tracks users whose stored bytes currently exceed their plan's cap.
A row is created by the reconciliation job on first detection of an
over-quota state, refreshed on subsequent scans while the breach
persists, and deleted when the user either frees up space (drops
files) or upgrades into compliance.

``user_id`` is UNIQUE — at most one open breach per user. Grace
counts from ``detected_at`` (preserved across refreshes) so a user
oscillating just above the cap cannot reset their countdown by
shrinking-then-growing. ``last_notified_at`` gates the per-user
notification cooldown (see ``OVER_QUOTA_NOTIFICATION_COOLDOWN_DAYS``
in ``learnic/entities/billing/constants.py``).

Revision ID: s2breach0001
Revises: s1bill0001
Create Date: 2026-05-20 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "s2breach0001"
down_revision: Union[str, Sequence[str], None] = "s1bill0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of ``PLAN_CODE_MAX_LEN`` from
# ``learnic/entities/billing/constants.py``. Migrations are frozen,
# the literal is duplicated here intentionally.
_PLAN_CODE_MAX_LEN = 32


def upgrade() -> None:
    """Create ``storage_quota_breaches`` table."""
    op.create_table(
        "storage_quota_breaches",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "plan_code",
            sa.String(_PLAN_CODE_MAX_LEN),
            nullable=False,
        ),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("over_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "last_notified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    """Drop the table."""
    op.drop_table("storage_quota_breaches")
