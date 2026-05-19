"""add subscriptions table

Adds the ``subscriptions`` table: one row per grant of a tariff
("BETA" today; later "PRO" / "TEAM" / …) to a user. Each grant is
INSERTed as a new row — the "current" subscription is the most
recent row that's both unrevoked and unexpired. Absence of any
active row means the user falls back to the in-code FREE plan
(see ``learnic/entities/billing/plan.py``).

No FK from ``subscriptions.plan_code`` to a ``plans`` table —
plans live in code, not in the DB. Drift between
``subscriptions.plan_code`` and the in-code registry is surfaced
loudly at read time via ``UnknownPlanCodeError``.

Revision ID: s1bill0001
Revises: r1file0001
Create Date: 2026-05-19 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "s1bill0001"
down_revision: Union[str, Sequence[str], None] = "r1file0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of ``PLAN_CODE_MAX_LEN`` from
# ``learnic/entities/billing/constants.py``. Migrations are frozen so
# the literal is duplicated here intentionally.
_PLAN_CODE_MAX_LEN = 32


def upgrade() -> None:
    """Create ``subscriptions`` table + lookup index."""
    op.create_table(
        "subscriptions",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "plan_code",
            sa.String(_PLAN_CODE_MAX_LEN),
            nullable=False,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("granted_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.oid"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"],
            ["users.oid"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )
    # "Current subscription for user" query plan: scans rows for the
    # user, filters by revoked_at IS NULL and expires_at predicate,
    # picks the most recent granted_at. The index lets that filter
    # happen on an index scan rather than a seq scan of the table.
    op.create_index(
        "ix_subscriptions_user_active",
        "subscriptions",
        ["user_id", "revoked_at", "expires_at"],
    )


def downgrade() -> None:
    """Drop the table and its index."""
    op.drop_index("ix_subscriptions_user_active", table_name="subscriptions")
    op.drop_table("subscriptions")
