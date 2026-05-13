"""add users.is_verified

Adds a public "verified" flag on users, distinct from
``email_verified`` (which tracks login-email confirmation). This is
the badge surfaced on avatars across the SPA.

Revision ID: a1b8cde6f7a0
Revises: b1c2d3e4f5a7
Create Date: 2026-05-12 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a1b8cde6f7a0"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_verified")
