"""rename notification category 'invites' → 'teaching'

The category was renamed in the domain to better describe what it
covers — every notification kind shipped today (invite_sent,
invite_accepted, invite_declined, access_revoked) is part of the
teaching surface, and the original ``invites`` label was scoped
too narrow once ``access_revoked`` joined the set.

This migration:

1. Renames the PG enum value ``notification_category.invites`` to
   ``teaching`` (Postgres 10+ supports ``ALTER TYPE … RENAME VALUE``,
   so existing ``notifications.category`` rows are updated in place).
2. Renames the wide columns on ``notification_preferences`` —
   ``push_invites`` → ``push_teaching``, ``email_invites`` →
   ``email_teaching``. ``ALTER TABLE … RENAME COLUMN`` preserves
   the per-user values; no data is dropped.

Revision ID: t4a1b2c3d4e9
Revises: s3a1b2c3d4e8
Create Date: 2026-05-10 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "t4a1b2c3d4e9"
down_revision: Union[str, Sequence[str], None] = "s3a1b2c3d4e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE notification_category RENAME VALUE 'invites' TO 'teaching'",
    )
    op.alter_column(
        "notification_preferences",
        "push_invites",
        new_column_name="push_teaching",
    )
    op.alter_column(
        "notification_preferences",
        "email_invites",
        new_column_name="email_teaching",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "notification_preferences",
        "email_teaching",
        new_column_name="email_invites",
    )
    op.alter_column(
        "notification_preferences",
        "push_teaching",
        new_column_name="push_invites",
    )
    op.execute(
        "ALTER TYPE notification_category RENAME VALUE 'teaching' TO 'invites'",
    )
