"""add refresh token device metadata

Revision ID: f4c8b921a503
Revises: e1b9c4d72a08
Create Date: 2026-05-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "f4c8b921a503"
down_revision: Union[str, Sequence[str], None] = "e1b9c4d72a08"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "refresh_tokens",
        sa.Column("ip_address", postgresql.INET(), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("user_agent", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "refresh_tokens",
        sa.Column("device_label", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("refresh_tokens", "device_label")
    op.drop_column("refresh_tokens", "user_agent")
    op.drop_column("refresh_tokens", "ip_address")
