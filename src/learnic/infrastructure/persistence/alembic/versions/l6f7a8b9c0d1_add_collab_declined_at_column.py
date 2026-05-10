"""add declined_at column + rebuild collaborator-active index

Adds the ``declined_at`` timestamp column on
``product_collaborations`` and rebuilds the partial unique
index that prevents two non-terminal collaborations for the
same ``(product, user)`` pair so it excludes both
``'revoked'`` and ``'declined'`` rows — both are terminal and
a fresh invite is allowed against either.

Split from ``k5e6f7a8b9c0`` because PostgreSQL refuses to use
a new enum value inside the same transaction it was added in;
the parent migration commits the enum addition first, then
this one references the new value safely.

Revision ID: l6f7a8b9c0d1
Revises: k5e6f7a8b9c0
Create Date: 2026-05-09 12:00:00.000001

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "l6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "k5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "product_collaborations",
        sa.Column(
            "declined_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.drop_index(
        "uq_collab_product_collaborator_active",
        table_name="product_collaborations",
    )
    op.create_index(
        "uq_collab_product_collaborator_active",
        "product_collaborations",
        ["product_id", "collaborator_id"],
        unique=True,
        postgresql_where=sa.text(
            "collaborator_id IS NOT NULL "
            "AND status NOT IN ('revoked', 'declined')",
        ),
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the partial-index variant and ``declined_at`` column.
    The enum value cannot be removed in PostgreSQL without
    rewriting every row that uses it; downgrade promotes such
    rows to ``revoked`` (semantically the closest terminal
    state) before recreating the original ``status != 'revoked'``
    index. The enum value itself is left in place — Postgres
    cannot drop enum members without recreating the type.
    """
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE product_collaborations "
            "SET status = 'revoked', "
            "    revoked_at = COALESCE(revoked_at, declined_at, NOW()) "
            "WHERE status = 'declined'",
        ),
    )
    op.drop_index(
        "uq_collab_product_collaborator_active",
        table_name="product_collaborations",
    )
    op.create_index(
        "uq_collab_product_collaborator_active",
        "product_collaborations",
        ["product_id", "collaborator_id"],
        unique=True,
        postgresql_where=sa.text(
            "collaborator_id IS NOT NULL AND status != 'revoked'",
        ),
    )
    op.drop_column("product_collaborations", "declined_at")
