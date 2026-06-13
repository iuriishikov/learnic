"""add user search (tsvector + trigram over name fields)

Mirrors the product full-text/fuzzy search (``ad03search0001``) for the
user name search powering ``GET /users/search`` and
``GET /admin/users/search``. Replaces the previous plain ``ILIKE``
substring match with morphology-aware ranking + typo tolerance.

Two columns are added to ``users``:

* ``search_vector`` (``tsvector``) — Russian-language FTS with field
  weights: ``A`` for ``last_name``, ``B`` for ``first_name``, ``C`` for
  ``patronymic`` (surname-first ranking, matching Russian search habit).
* ``search_text`` (``text``, lower-cased) — the same three fields
  concatenated, GIN-indexed with ``gin_trgm_ops`` for the trigram fuzzy
  fallback via ``%>`` / ``word_similarity()``.

Both are rebuilt by ``refresh_user_search(uid)`` inside a single trigger
on ``users`` AFTER INSERT OR UPDATE OF the three name fields — there is
no cross-table fan-out (unlike products, whose vector also depends on
author + tags), so the trigger surface is just this one table.

``pg_trgm`` already exists from ``ad03search0001``; the ``CREATE
EXTENSION IF NOT EXISTS`` is idempotent and kept for standalone replay.

Revision ID: usrsearch0001
Revises: notedel0001
Create Date: 2026-06-12 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "usrsearch0001"
down_revision: Union[str, Sequence[str], None] = "notedel0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_REFRESH_FN_SQL = """
CREATE OR REPLACE FUNCTION refresh_user_search(uid uuid)
RETURNS void
LANGUAGE sql
AS $$
  UPDATE users u SET
    search_text = lower(
      coalesce(u.last_name, '') || ' ' ||
      coalesce(u.first_name, '') || ' ' ||
      coalesce(u.patronymic, '')
    ),
    search_vector =
      setweight(to_tsvector('russian', coalesce(u.last_name, '')), 'A') ||
      setweight(to_tsvector('russian', coalesce(u.first_name, '')), 'B') ||
      setweight(to_tsvector('russian', coalesce(u.patronymic, '')), 'C')
  WHERE u.oid = uid;
$$;
"""

_TRG_FN_SQL = """
CREATE OR REPLACE FUNCTION trg_users_search_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM refresh_user_search(NEW.oid);
  RETURN NULL;
END;
$$;
"""


def upgrade() -> None:
    """Add the search columns, refresh trigger, GIN indexes, backfill."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "users",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("search_text", sa.Text(), nullable=True),
    )

    op.execute(_REFRESH_FN_SQL)
    op.execute(_TRG_FN_SQL)
    op.execute(
        """
        CREATE TRIGGER trg_users_search
          AFTER INSERT OR UPDATE OF first_name, last_name, patronymic
          ON users
          FOR EACH ROW
          EXECUTE FUNCTION trg_users_search_refresh();
        """,
    )

    op.create_index(
        "ix_users_search_vector",
        "users",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_users_search_text_trgm",
        "users",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    # Backfill existing rows — one UPDATE per row via the helper. Fine
    # for the current user count; rewrite as one bulk UPDATE if the
    # table grows past ~100k rows.
    op.execute("SELECT refresh_user_search(oid) FROM users")


def downgrade() -> None:
    """Drop the trigger, function, indexes and columns."""
    op.execute("DROP TRIGGER IF EXISTS trg_users_search ON users")
    op.execute("DROP FUNCTION IF EXISTS trg_users_search_refresh()")
    op.execute("DROP FUNCTION IF EXISTS refresh_user_search(uuid)")
    op.drop_index("ix_users_search_text_trgm", table_name="users")
    op.drop_index("ix_users_search_vector", table_name="users")
    op.drop_column("users", "search_text")
    op.drop_column("users", "search_vector")
    # pg_trgm is shared with product search — do NOT drop it here.
