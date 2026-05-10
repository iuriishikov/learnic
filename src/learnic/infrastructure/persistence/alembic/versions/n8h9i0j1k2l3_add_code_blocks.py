"""add code lesson blocks (draft + release snapshot tables)

Adds the ``code`` value to the ``lesson_block_type`` enum and
creates a pair of provider-specific child tables — ``code_blocks``
on the draft side and ``course_release_code_blocks`` on the
release-snapshot side. The initial schema stored a single
``(source, language)`` pair per row; the follow-up migration
``o9j0k1l2m3n4`` converts that to a ``tabs`` JSONB array so a
single block can carry variant snippets (npm / pnpm / yarn).

Revision ID: n8h9i0j1k2l3
Revises: m7g8h9i0j1k2
Create Date: 2026-05-09 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "n8h9i0j1k2l3"
down_revision: Union[str, Sequence[str], None] = "m7g8h9i0j1k2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Add the ``code`` value to ``lesson_block_type`` and create the
    two backing child tables (draft + release snapshot). PG 12+
    supports ``ALTER TYPE ... ADD VALUE`` inside a transaction; the
    rest of the migration commits in the same tx.
    """
    op.execute(
        "ALTER TYPE lesson_block_type ADD VALUE IF NOT EXISTS 'code'",
    )

    op.create_table(
        "code_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=200_000), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["lesson_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )

    op.create_table(
        "course_release_code_blocks",
        sa.Column("oid", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=200_000), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["oid"],
            ["course_release_blocks.oid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("oid"),
    )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL has no ``ALTER TYPE ... DROP VALUE``; recreate the
    enum without ``code`` after deleting any rows that use it on
    both the draft and snapshot sides.
    """
    op.execute("DELETE FROM course_release_blocks WHERE type = 'code'")
    op.execute("DELETE FROM lesson_blocks WHERE type = 'code'")
    op.drop_table("course_release_code_blocks")
    op.drop_table("code_blocks")

    op.execute("ALTER TYPE lesson_block_type RENAME TO lesson_block_type_old")
    op.execute(
        "CREATE TYPE lesson_block_type AS ENUM ('html', 'katex', 'rutube_video')",
    )
    op.execute(
        "ALTER TABLE lesson_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute(
        "ALTER TABLE course_release_blocks "
        "ALTER COLUMN type TYPE lesson_block_type "
        "USING type::text::lesson_block_type",
    )
    op.execute("DROP TYPE lesson_block_type_old")
