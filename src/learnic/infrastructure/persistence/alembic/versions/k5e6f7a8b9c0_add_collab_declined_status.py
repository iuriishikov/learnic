"""add DECLINED collaboration status enum value

Adds the ``'declined'`` value to the
``product_collaboration_status`` enum so the recipient of an
in-app invite can explicitly reject it via
``POST /collaborations/{id}/decline-in-app``. The companion
``declined_at`` column and the rebuilt partial unique index
that excludes the new terminal state live in the next
migration (``l6f7a8b9c0d1``) — PostgreSQL refuses to use a new
enum value inside the same transaction it was added in, so
the value must commit before any DDL can reference it.

Revision ID: k5e6f7a8b9c0
Revises: j4d5e6f7a8b9
Create Date: 2026-05-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "k5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "j4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE product_collaboration_status ADD VALUE IF NOT EXISTS "
        "'declined'",
    )


def downgrade() -> None:
    """Downgrade schema.

    No-op: PostgreSQL cannot drop an enum member without
    recreating the type (and rewriting every row that uses it).
    The companion migration handles row promotion when going
    down, so by the time this one runs the value is already
    unused — leaving it in place is harmless.
    """
