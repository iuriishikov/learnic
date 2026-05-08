"""add role position for hierarchy enforcement

Adds the ``position`` column to ``roles`` and backfills it. System
roles take their fixed seed positions (Moderator=100, Editor=200,
Commentor=300, Viewer=400). Custom roles get a dense position
sequence per product, computed from ``created_at`` so they slot
below the system roles in the order they were originally created
— this preserves intent without requiring an out-of-band manual
fix-up.

Revision ID: g1a2b3c4d5e6
Revises: f4c8b921a503
Create Date: 2026-05-08 12:00:00.000000

"""

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "g1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "f4c8b921a503"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_VIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_COMMENTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
_EDITOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
_MODERATOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")

_SYSTEM_POSITIONS: dict[uuid.UUID, int] = {
    _MODERATOR_ID: 100,
    _EDITOR_ID: 200,
    _COMMENTOR_ID: 300,
    _VIEWER_ID: 400,
}

# Spacing between custom roles within a product so future inserts
# can slot in without a global re-pack.
_CUSTOM_BASE = 1000
_CUSTOM_STEP = 10


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add nullable column so existing rows keep their value.
    op.add_column("roles", sa.Column("position", sa.Integer(), nullable=True))

    bind = op.get_bind()

    # 2. Backfill system roles by their stable UUIDs.
    for role_id, position in _SYSTEM_POSITIONS.items():
        bind.execute(
            sa.text("UPDATE roles SET position = :p WHERE oid = :oid"),
            {"p": position, "oid": role_id},
        )

    # 3. Backfill custom roles per-product, ordered by created_at.
    products = bind.execute(
        sa.text(
            "SELECT DISTINCT product_id FROM roles "
            "WHERE product_id IS NOT NULL AND position IS NULL"
        )
    ).fetchall()
    for (product_id,) in products:
        rows = bind.execute(
            sa.text(
                "SELECT oid FROM roles "
                "WHERE product_id = :pid AND position IS NULL "
                "ORDER BY created_at ASC, oid ASC"
            ),
            {"pid": product_id},
        ).fetchall()
        for index, (role_id,) in enumerate(rows):
            bind.execute(
                sa.text("UPDATE roles SET position = :p WHERE oid = :oid"),
                {
                    "p": _CUSTOM_BASE + index * _CUSTOM_STEP,
                    "oid": role_id,
                },
            )

    # 4. Lock the column down — every row must now have a value.
    op.alter_column("roles", "position", nullable=False)

    # 5. Helpful index for hierarchy lookups (joined with grants).
    op.create_index("ix_roles_position", "roles", ["position"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_roles_position", table_name="roles")
    op.drop_column("roles", "position")
