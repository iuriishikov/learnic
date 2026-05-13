"""add access_revoked notification kind enum value

Adds the ``'access_revoked'`` value to the ``notification_kind``
enum so the subtype table created by the next migration
(``s3a1b2c3d4e8``) can reference it. PostgreSQL refuses to use a
freshly-added enum value inside the same transaction it was
created in — same rationale as the
``invite_declined`` split (``p0a1b2c3d4e5`` → ``q1a1b2c3d4e6``).

Revision ID: r2a1b2c3d4e7
Revises: q1a1b2c3d4e6
Create Date: 2026-05-10 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "r2a1b2c3d4e7"
down_revision: Union[str, Sequence[str], None] = "q1a1b2c3d4e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'access_revoked'",
    )


def downgrade() -> None:
    """Downgrade schema.

    No-op: PostgreSQL cannot drop an enum member without
    recreating the type. The companion migration drops the
    subtype table that uses this value, so by the time this one
    runs the value is unused — leaving it in place is harmless.
    """
