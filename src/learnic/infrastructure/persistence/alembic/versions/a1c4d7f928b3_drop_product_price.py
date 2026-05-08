"""drop product price columns

Revision ID: a1c4d7f928b3
Revises: f8b2d4e6a127
Create Date: 2026-04-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c4d7f928b3"
down_revision: Union[str, Sequence[str], None] = "f8b2d4e6a127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("products", "price_currency")
    op.drop_column("products", "price_amount")
    op.execute("DROP TYPE currency")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "CREATE TYPE currency AS ENUM ('USD', 'EUR', 'RUB', 'KZT', 'BYN')",
    )
    op.add_column(
        "products",
        sa.Column(
            "price_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
    )
    op.add_column(
        "products",
        sa.Column(
            "price_currency",
            sa.Enum("USD", "EUR", "RUB", "KZT", "BYN", name="currency"),
            nullable=False,
        ),
    )
