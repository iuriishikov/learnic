"""add function-graph lesson blocks (draft + release snapshot tables)

Adds the ``function_graph`` value to the ``lesson_block_type`` enum and
creates a pair of child tables — ``function_graph_blocks`` on the draft
side and ``note_release_function_graph_blocks`` on the release-snapshot
side. Each holds a single opaque JSONB ``config`` column carrying the
whole GeoGebra-like graph spec (functions / curves / points / parameter
sliders / viewport / axes), validated upstream by ``GraphConfig``.

Revision ID: fngraph0001
Revises: nbansw0001
Create Date: 2026-06-08 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "fngraph0001"
down_revision: Union[str, Sequence[str], None] = "nbansw0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Add the ``function_graph`` value to ``lesson_block_type`` and
    create the two backing child tables (draft + release snapshot).
    PG 12+ supports ``ALTER TYPE ... ADD VALUE`` inside a transaction;
    the new value is not *used* in this migration, so the same-tx
    restriction does not apply.
    """
    op.execute(
        "ALTER TYPE lesson_block_type "
        "ADD VALUE IF NOT EXISTS 'function_graph'",
    )

    op.create_table(
        "function_graph_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "note_release_function_graph_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["note_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL has no ``ALTER TYPE ... DROP VALUE``; recreate the enum
    without ``function_graph`` after deleting any rows that use it on
    both the draft and snapshot sides.
    """
    op.execute(
        "DELETE FROM note_release_blocks WHERE type = 'function_graph'",
    )
    op.execute("DELETE FROM lesson_blocks WHERE type = 'function_graph'")
    op.drop_table("note_release_function_graph_blocks")
    op.drop_table("function_graph_blocks")

    op.execute(
        "ALTER TYPE lesson_block_type RENAME TO lesson_block_type_old",
    )
    op.execute(
        "CREATE TYPE lesson_block_type AS ENUM ("
        "'html', 'katex', 'rutube_video', 'code', "
        "'single_choice', 'multi_choice', 'text_input', "
        "'file', 'video_file', 'photo_collage')",
    )
    op.execute(
        "ALTER TABLE lesson_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute(
        "ALTER TABLE note_release_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute("DROP TYPE lesson_block_type_old")
