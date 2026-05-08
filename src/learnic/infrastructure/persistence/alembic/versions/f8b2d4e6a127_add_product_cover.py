"""add product cover_file_id

Revision ID: f8b2d4e6a127
Revises: f7a3c042e8d9
Create Date: 2026-04-29 03:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f8b2d4e6a127"
down_revision: Union[str, Sequence[str], None] = "f7a3c042e8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "products",
        sa.Column("cover_file_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_products_cover_file_id",
        "products",
        "files",
        ["cover_file_id"],
        ["oid"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_products_cover_file_id",
        "products",
        type_="foreignkey",
    )
    op.drop_column("products", "cover_file_id")
