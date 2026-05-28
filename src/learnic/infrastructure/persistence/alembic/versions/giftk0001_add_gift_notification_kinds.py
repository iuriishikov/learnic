"""add gift notification kind enum values

Adds ``'gift_received'`` / ``'gift_accepted'`` / ``'gift_declined'``
to the ``notification_kind`` enum so the subtype tables created by
the next migration (``giftt0002``) can reference them. PostgreSQL
refuses to use a freshly-added enum value inside the same
transaction it was created in — same split rationale as the
``access_revoked`` kind (``r2a1b2c3d4e7`` → ``s3a1b2c3d4e8``).

Revision ID: giftk0001
Revises: z3collage0002
Create Date: 2026-05-25 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "giftk0001"
down_revision: Union[str, Sequence[str], None] = "z3collage0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'gift_received'",
    )
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'gift_accepted'",
    )
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'gift_declined'",
    )


def downgrade() -> None:
    """Downgrade schema.

    No-op: PostgreSQL cannot drop an enum member without recreating
    the type. The companion migration drops the subtype tables that
    use these values, so by the time this one runs they are unused —
    leaving them in place is harmless.
    """
