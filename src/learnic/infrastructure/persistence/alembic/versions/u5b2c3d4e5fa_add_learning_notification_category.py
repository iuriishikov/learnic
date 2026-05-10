"""add notification category 'learning'

Introduces the student-side counterpart to ``teaching``. The
category covers events that surface to a learner (course
progress, deadlines, instructor messages, future content events
on courses they are enrolled in). No notification kind maps to
it yet; the column and enum slot land first so newly-added
kinds slot in without another migration.

This migration:

1. Appends ``learning`` to the ``notification_category`` PG enum
   via ``ALTER TYPE … ADD VALUE``. Postgres 12+ allows this
   inside a transaction, matching the rest of the migration
   chain.
2. Adds ``push_learning`` (default ``true``) and
   ``email_learning`` (default ``false``) wide columns on
   ``notification_preferences`` so the existing per-user rows
   pick up the same defaults the entity applies for new users.

Revision ID: u5b2c3d4e5fa
Revises: t4a1b2c3d4e9
Create Date: 2026-05-10 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "u5b2c3d4e5fa"
down_revision: Union[str, Sequence[str], None] = "t4a1b2c3d4e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'learning'",
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "push_learning",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "email_learning",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    The columns drop cleanly. The PG enum value is left in place:
    ``ALTER TYPE … DROP VALUE`` does not exist, and rebuilding
    the enum to remove a label would require rewriting every
    ``notifications.category`` row. Since no rows reference
    ``learning`` until a kind is wired to it, the orphan label
    is harmless.
    """
    op.drop_column("notification_preferences", "email_learning")
    op.drop_column("notification_preferences", "push_learning")
