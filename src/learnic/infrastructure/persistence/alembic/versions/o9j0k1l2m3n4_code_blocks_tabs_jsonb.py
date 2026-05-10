"""convert code blocks to JSONB tabs

Replaces the per-row ``(source, language)`` pair on ``code_blocks``
and ``course_release_code_blocks`` with a single ``tabs`` JSONB
array of ``{"label", "source", "language"}`` objects. This lets a
single code block carry variant snippets (npm / pnpm / yarn,
``Component.tsx`` / ``test.spec.tsx``) without an extra child
table — the application layer never queries inside the array, so
denormalization is the right trade.

Existing rows are migrated in-place: each surviving block becomes
a one-tab list with an empty label (the read-mode tab strip is
hidden when there's only one tab, so existing single-snippet
blocks render exactly as before).

Revision ID: o9j0k1l2m3n4
Revises: n8h9i0j1k2l3
Create Date: 2026-05-09 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "o9j0k1l2m3n4"
down_revision: Union[str, Sequence[str], None] = "n8h9i0j1k2l3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES: tuple[str, ...] = ("code_blocks", "course_release_code_blocks")


def upgrade() -> None:
    """Upgrade schema.

    For each table:

    1. Add ``tabs`` JSONB column (nullable, so existing rows survive).
    2. Backfill: ``tabs = jsonb_build_array(jsonb_build_object(
       'label', '', 'source', source, 'language', language))``.
    3. Set NOT NULL on ``tabs``.
    4. Drop the old ``source`` and ``language`` columns.

    Steps 1-3 are wrapped in a transaction; PostgreSQL ALTERs are
    cheap because the tables are small (one row per code block).
    """
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("tabs", JSONB(), nullable=True),
        )
        op.execute(
            f"""
            UPDATE {table}
            SET tabs = jsonb_build_array(
                jsonb_build_object(
                    'label', '',
                    'source', source,
                    'language', language
                )
            )
            """,
        )
        op.alter_column(table, "tabs", nullable=False)
        op.drop_column(table, "language")
        op.drop_column(table, "source")


def downgrade() -> None:
    """Downgrade schema.

    Restores the ``(source, language)`` shape by reading the FIRST
    tab of each block. Multi-tab blocks lose their additional tabs
    on downgrade — there's no faithful way to fold variants back
    into a single pair, and downgrades are a recovery path, not a
    routine operation.
    """
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column("source", sa.String(length=200_000), nullable=True),
        )
        op.add_column(
            table,
            sa.Column("language", sa.String(length=16), nullable=True),
        )
        op.execute(
            f"""
            UPDATE {table}
            SET source = COALESCE(tabs->0->>'source', ''),
                language = COALESCE(tabs->0->>'language', 'plain')
            """,
        )
        op.alter_column(table, "source", nullable=False)
        op.alter_column(table, "language", nullable=False)
        op.drop_column(table, "tabs")
