"""add rutube_video_blocks

Revision ID: f1d8b62a4e07
Revises: e7a3c1f5b918
Create Date: 2026-05-01 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1d8b62a4e07"
down_revision: Union[str, Sequence[str], None] = "e7a3c1f5b918"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Adds the ``rutube_video`` value to the ``lesson_block_type`` enum
    and creates a provider-specific child table. There is no
    unified ``video_blocks`` / ``video_provider`` abstraction —
    each external embed provider gets its own block type and child
    table.
    """
    # PG 12+ supports ALTER TYPE ... ADD VALUE inside a transaction; the
    # rest of the migration (table creation) commits in the same tx.
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'rutube_video'",
    )

    op.create_table(
        "rutube_video_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column(
            "external_id",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "title",
            sa.String(length=200),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL has no ``ALTER TYPE ... DROP VALUE``; recreate the
    enum without ``rutube_video`` after deleting any rows that use it.
    """
    op.execute("DELETE FROM lesson_blocks WHERE type = 'rutube_video'")
    op.drop_table("rutube_video_blocks")

    op.execute("ALTER TYPE lesson_block_type RENAME TO lesson_block_type_old")
    op.execute("CREATE TYPE lesson_block_type AS ENUM ('html', 'latex')")
    op.execute(
        "ALTER TABLE lesson_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute("DROP TYPE lesson_block_type_old")
