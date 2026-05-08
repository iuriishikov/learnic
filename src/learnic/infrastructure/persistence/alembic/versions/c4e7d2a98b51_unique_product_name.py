"""make products.name unique per author

Revision ID: c4e7d2a98b51
Revises: b3f5a8d109cc
Create Date: 2026-04-30 18:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "c4e7d2a98b51"
down_revision: Union[str, Sequence[str], None] = "b3f5a8d109cc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_unique_constraint(
        "uq_products_author_id_name",
        "products",
        ["author_id", "name"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_products_author_id_name",
        "products",
        type_="unique",
    )
