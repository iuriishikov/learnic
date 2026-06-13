"""add tag search (tsvector + trigram over name)

Mirrors the user (``usrsearch0001``) and product (``ad03search0001``)
search for the tag autocomplete behind ``GET /tags``. Replaces the
plain ``slug LIKE '%q%'`` substring match with morphology-aware
ranking + typo tolerance over the human-readable ``name``.

Two columns are added to ``tags``:

* ``search_vector`` (``tsvector``) — Russian-language FTS over ``name``.
* ``search_text`` (``text``, lower-cased ``name``) — GIN-indexed with
  ``gin_trgm_ops`` for the trigram fuzzy fallback (``%>`` /
  ``word_similarity``).

Both are rebuilt by ``refresh_tag_search(tid)`` inside one trigger on
``tags`` AFTER INSERT OR UPDATE OF ``name`` — a single field, no
cross-table fan-out.

``pg_trgm`` already exists from ``ad03search0001``; the ``CREATE
EXTENSION IF NOT EXISTS`` is idempotent and kept for standalone replay.

Revision ID: tagsearch0001
Revises: usrsearch0001
Create Date: 2026-06-12 19:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "tagsearch0001"
down_revision: Union[str, Sequence[str], None] = "usrsearch0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REFRESH_FN_SQL = """
CREATE OR REPLACE FUNCTION refresh_tag_search(tid uuid)
RETURNS void
LANGUAGE sql
AS $$
  UPDATE tags t SET
    search_text = lower(coalesce(t.name, '')),
    search_vector = to_tsvector('russian', coalesce(t.name, ''))
  WHERE t.oid = tid;
$$;
"""

_TRG_FN_SQL = """
CREATE OR REPLACE FUNCTION trg_tags_search_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM refresh_tag_search(NEW.oid);
  RETURN NULL;
END;
$$;
"""


def upgrade() -> None:
    """Add the search columns, refresh trigger, GIN indexes, backfill."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "tags",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.add_column(
        "tags",
        sa.Column("search_text", sa.Text(), nullable=True),
    )

    op.execute(_REFRESH_FN_SQL)
    op.execute(_TRG_FN_SQL)
    op.execute(
        """
        CREATE TRIGGER trg_tags_search
          AFTER INSERT OR UPDATE OF name
          ON tags
          FOR EACH ROW
          EXECUTE FUNCTION trg_tags_search_refresh();
        """,
    )

    op.create_index(
        "ix_tags_search_vector",
        "tags",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_tags_search_text_trgm",
        "tags",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    op.execute("SELECT refresh_tag_search(oid) FROM tags")


def downgrade() -> None:
    """Drop the trigger, function, indexes and columns."""
    op.execute("DROP TRIGGER IF EXISTS trg_tags_search ON tags")
    op.execute("DROP FUNCTION IF EXISTS trg_tags_search_refresh()")
    op.execute("DROP FUNCTION IF EXISTS refresh_tag_search(uuid)")
    op.drop_index("ix_tags_search_text_trgm", table_name="tags")
    op.drop_index("ix_tags_search_vector", table_name="tags")
    op.drop_column("tags", "search_text")
    op.drop_column("tags", "search_vector")
    # pg_trgm is shared with product/user search — do NOT drop it here.
