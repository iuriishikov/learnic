"""defer_collage_position_unique

Make ``uq_photo_collage_items_block_position`` ``DEFERRABLE INITIALLY
DEFERRED`` so reorder UPDATEs that swap positions in one statement
don't violate the constraint mid-row — the check fires at COMMIT,
when every row already has its final position.

Postgres doesn't allow ``ALTER CONSTRAINT … DEFERRABLE`` on UNIQUE
constraints, so the only path is drop + recreate.

Revision ID: z3collage0002
Revises: z2collage0001
Create Date: 2026-05-20 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "z3collage0002"
down_revision: Union[str, Sequence[str], None] = "z2collage0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate the unique constraint with ``DEFERRABLE INITIALLY DEFERRED``."""
    op.execute(
        "ALTER TABLE photo_collage_items "
        "DROP CONSTRAINT uq_photo_collage_items_block_position",
    )
    op.execute(
        "ALTER TABLE photo_collage_items "
        "ADD CONSTRAINT uq_photo_collage_items_block_position "
        "UNIQUE (block_id, position) DEFERRABLE INITIALLY DEFERRED",
    )


def downgrade() -> None:
    """Restore the immediate-check unique constraint."""
    op.execute(
        "ALTER TABLE photo_collage_items "
        "DROP CONSTRAINT uq_photo_collage_items_block_position",
    )
    op.execute(
        "ALTER TABLE photo_collage_items "
        "ADD CONSTRAINT uq_photo_collage_items_block_position "
        "UNIQUE (block_id, position)",
    )
