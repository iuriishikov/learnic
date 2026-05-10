"""add notification category 'security' and 'new_login' kind enum value

Lands the discriminator + preference columns required by the
``new_login`` notification kind in a single migration. The
companion ``w7d4e5fab2_add_new_login_table`` migration then
creates the subtype table — split because PostgreSQL refuses to
use a freshly-added enum value inside the same transaction it
was created in (same rationale as the
``invite_declined`` / ``access_revoked`` splits).

This migration:

1. Appends ``security`` to the ``notification_category`` PG enum
   via ``ALTER TYPE … ADD VALUE``.
2. Appends ``new_login`` to the ``notification_kind`` PG enum so
   the next migration's subtype table can reference it.
3. Adds ``push_security`` (default ``true``) and
   ``email_security`` (default ``false``) wide columns on
   ``notification_preferences`` so the existing per-user rows
   pick up the same defaults the entity applies for new users.

Revision ID: v6c3d4e5fab1
Revises: u5b2c3d4e5fa
Create Date: 2026-05-10 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "v6c3d4e5fab1"
down_revision: Union[str, Sequence[str], None] = "u5b2c3d4e5fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TYPE notification_category ADD VALUE IF NOT EXISTS 'security'",
    )
    op.execute(
        "ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'new_login'",
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "push_security",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "notification_preferences",
        sa.Column(
            "email_security",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    The columns drop cleanly. The PG enum values are left in
    place: ``ALTER TYPE … DROP VALUE`` does not exist, and
    rebuilding the enum to remove a label would require rewriting
    every dependent row. Since the companion migration drops the
    subtype table that uses ``new_login``, the orphan label is
    harmless until a future rebuild is desired.
    """
    op.drop_column("notification_preferences", "email_security")
    op.drop_column("notification_preferences", "push_security")
