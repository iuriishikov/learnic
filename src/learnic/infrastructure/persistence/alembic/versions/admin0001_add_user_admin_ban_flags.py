"""add user admin and ban flags

Adds two boolean columns to ``users``:

* ``is_admin`` — platform-administrator capability (granted out-of-band
  via the ``learnic-admin grant-admin`` CLI).
* ``is_banned`` — blocks login and is set by the admin ban endpoint
  (which also revokes the user's sessions).

Both default to ``false`` so every existing user is a non-admin,
non-banned regular account after the migration.

Revision ID: admin0001
Revises: visib0001
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "admin0001"
down_revision: Union[str, Sequence[str], None] = "visib0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_banned",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_banned")
    op.drop_column("users", "is_admin")
