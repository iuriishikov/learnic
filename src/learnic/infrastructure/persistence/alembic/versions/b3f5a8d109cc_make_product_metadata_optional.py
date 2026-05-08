"""make product description and duration optional

Revision ID: b3f5a8d109cc
Revises: a1c4d7f928b3
Create Date: 2026-04-30 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "b3f5a8d109cc"
down_revision: Union[str, Sequence[str], None] = "a1c4d7f928b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("products", "description", nullable=True)
    op.alter_column("products", "total_duration_in_hours", nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("products", "total_duration_in_hours", nullable=False)
    op.alter_column("products", "description", nullable=False)
