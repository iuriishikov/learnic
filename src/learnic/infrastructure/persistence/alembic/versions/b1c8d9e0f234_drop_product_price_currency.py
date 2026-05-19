"""drop product price_currency column

Revision ID: b1c8d9e0f234
Revises: ad03search0001
Create Date: 2026-05-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b1c8d9e0f234"
down_revision: Union[str, Sequence[str], None] = "ad03search0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the per-product currency column.

    Products are denominated in the owner's account currency
    (RUB-only at this phase); storing currency per product was
    redundant and risked drift on a future account-currency
    change. The ``currency`` PG enum stays — orders and wallets
    still depend on it.
    """
    op.drop_constraint(
        "ck_products_price_pair",
        "products",
        type_="check",
    )
    op.drop_column("products", "price_currency")


def downgrade() -> None:
    """Re-add the column (nullable, no backfill)."""
    op.add_column(
        "products",
        sa.Column(
            "price_currency",
            postgresql.ENUM(name="currency", create_type=False),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_products_price_pair",
        "products",
        "(price_amount IS NULL) = (price_currency IS NULL)",
    )
