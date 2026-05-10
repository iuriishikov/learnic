"""add invite_declined notification kind enum value

Adds the ``'invite_declined'`` value to the ``notification_kind``
enum so the notification subtype table created by the next
migration (``q1a1b2c3d4e6``) can reference it. PostgreSQL refuses
to use a freshly-added enum value inside the same transaction it
was created in, so the value must commit before any DDL or DML
references it — same rationale as the
``product_collaboration_status`` split (``k5e6f7a8b9c0`` →
``l6f7a8b9c0d1``).

Revision ID: p0a1b2c3d4e5
Revises: o9j0k1l2m3n4
Create Date: 2026-05-10 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "p0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "o9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'invite_declined'",
    )


def downgrade() -> None:
    """Downgrade schema.

    No-op: PostgreSQL cannot drop an enum member without
    recreating the type (and rewriting every row that uses it).
    The companion migration drops the subtype table that uses
    this value, so by the time this one runs the value is
    unused — leaving it in place is harmless.
    """
