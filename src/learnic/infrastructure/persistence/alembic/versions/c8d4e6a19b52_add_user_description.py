"""add user description column

Revision ID: c8d4e6a19b52
Revises: b3e9a72c51ff
Create Date: 2026-04-22 03:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d4e6a19b52"
down_revision: Union[str, Sequence[str], None] = "b3e9a72c51ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "description")
