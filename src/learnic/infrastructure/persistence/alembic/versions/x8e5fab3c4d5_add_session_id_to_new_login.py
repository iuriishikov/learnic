"""add session_id to notification_new_login

Adds the refresh-token ``family_id`` to the ``new_login`` subtype
table so the notification panel can render an inline "Logout
from this device" CTA that hits
``DELETE /auth/sessions/{session_id}``.

Existing ``new_login`` rows pre-date the field and have no
session reference to backfill — there is no source-of-truth join
back to a refresh-token family for an already-issued
notification. The migration deletes them before adding the
column ``NOT NULL``; the cascade on
``(notifications.oid, notifications.kind)`` removes the matching
parent rows in ``notifications`` automatically.

Revision ID: x8e5fab3c4d5
Revises: w7d4e5fab2
Create Date: 2026-05-10 17:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "x8e5fab3c4d5"
down_revision: Union[str, Sequence[str], None] = "w7d4e5fab2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "DELETE FROM notifications WHERE kind = 'new_login'",
    )
    op.add_column(
        "notification_new_login",
        sa.Column("session_id", sa.Uuid(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("notification_new_login", "session_id")
