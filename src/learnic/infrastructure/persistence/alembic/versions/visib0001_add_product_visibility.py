"""add product visibility (public/private)

Adds the ``product_visibility`` enum and a ``visibility`` column to
``products``. Visibility is orthogonal to ``status``: a product can be
``PUBLISHED`` yet ``PRIVATE``. ``PUBLIC`` is the default so every
pre-existing product keeps showing up in the catalog/search exactly as
before; ``PRIVATE`` products are hidden from discovery and reachable
only through a gift/invite.

Revision ID: visib0001
Revises: giftt0002
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "visib0001"
down_revision: Union[str, Sequence[str], None] = "giftt0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PRODUCT_VISIBILITY = postgresql.ENUM(
    "public",
    "private",
    name="product_visibility",
)


def upgrade() -> None:
    bind = op.get_bind()
    _PRODUCT_VISIBILITY.create(bind, checkfirst=True)
    op.add_column(
        "products",
        sa.Column(
            "visibility",
            postgresql.ENUM(
                "public",
                "private",
                name="product_visibility",
                create_type=False,
            ),
            nullable=False,
            server_default="public",
        ),
    )


def downgrade() -> None:
    op.drop_column("products", "visibility")
    op.execute("DROP TYPE product_visibility")
