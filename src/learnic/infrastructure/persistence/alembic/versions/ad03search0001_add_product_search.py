"""add product search (tsvector + trigram, multi-field with weights)

Postgres-only full-text + fuzzy search across product ``name``,
author full name (first + last + patronymic), attached tag names,
and HTML-stripped ``description``. No external search service —
everything stays inside the same DB that ``docker-compose.dev.yaml``
already runs.

Two columns are added to ``products``:

* ``search_vector`` (``tsvector``) — Russian-language FTS with field
  weights: ``A`` for name, ``B`` for author full name AND tag names,
  ``C`` for the HTML-stripped description. Drives morphology-aware
  ranking via ``ts_rank_cd`` (e.g. "курсы" matches "курс").
* ``search_text`` (``text``, lower-cased) — concatenation of the same
  four fields. GIN-indexed with ``gin_trgm_ops`` to drive fuzzy
  fallback for typos via ``%`` / ``similarity()`` from ``pg_trgm``.

Both columns are populated by ``refresh_product_search(pid)``, which
runs inside four triggers — synchronously, in the same transaction
as the originating mutation, so by the time the API returns
``200 OK`` the search index is already current:

* on ``products`` after INSERT or UPDATE OF (name, description,
  author_id) — refresh the affected row.
* on ``product_tags`` after INSERT or DELETE — refresh the product
  whose tag set changed.
* on ``tags`` after UPDATE OF (name) — refresh every product that
  carries the renamed tag.
* on ``users`` after UPDATE OF (first_name, last_name, patronymic)
  — refresh every product authored by this user.

Backfill at the end iterates ``SELECT refresh_product_search(oid)
FROM products``. Single-row updates through the helper are slow on
millions of rows but fine for the current catalog; if/when the
products table outgrows that, rewrite the backfill as one bulk
UPDATE joining tags/users.

Revision ID: ad03search0001
Revises: ac02merge0001
Create Date: 2026-05-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "ad03search0001"
down_revision: Union[str, Sequence[str], None] = "ac02merge0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STRIP_HTML_FN_SQL = r"""
CREATE OR REPLACE FUNCTION strip_html(t text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  SELECT regexp_replace(
    regexp_replace(coalesce(t, ''), '<[^>]+>', ' ', 'g'),
    '\s+', ' ', 'g'
  );
$$;
"""

# One-row UPDATE that rebuilds both search columns from current
# product + author + tag set. Author and tag-name lookups are
# correlated subqueries on ``p.oid`` / ``p.author_id`` so Postgres
# executes each once for the single targeted row.
_REFRESH_FN_SQL = """
CREATE OR REPLACE FUNCTION refresh_product_search(pid uuid)
RETURNS void
LANGUAGE sql
AS $$
  UPDATE products p SET
    search_text = lower(
      coalesce(p.name, '') || ' ' ||
      coalesce((
        SELECT coalesce(u.first_name, '') || ' ' ||
               coalesce(u.last_name, '') || ' ' ||
               coalesce(u.patronymic, '')
        FROM users u WHERE u.oid = p.author_id
      ), '') || ' ' ||
      coalesce((
        SELECT coalesce(string_agg(t.name, ' '), '')
        FROM product_tags pt JOIN tags t ON t.oid = pt.tag_id
        WHERE pt.product_id = p.oid
      ), '') || ' ' ||
      strip_html(coalesce(p.description, ''))
    ),
    search_vector =
      setweight(
        to_tsvector('russian', coalesce(p.name, '')),
        'A'
      ) ||
      setweight(
        to_tsvector('russian',
          coalesce((
            SELECT coalesce(u.first_name, '') || ' ' ||
                   coalesce(u.last_name, '') || ' ' ||
                   coalesce(u.patronymic, '')
            FROM users u WHERE u.oid = p.author_id
          ), '')
        ),
        'B'
      ) ||
      setweight(
        to_tsvector('russian',
          coalesce((
            SELECT coalesce(string_agg(t.name, ' '), '')
            FROM product_tags pt JOIN tags t ON t.oid = pt.tag_id
            WHERE pt.product_id = p.oid
          ), '')
        ),
        'B'
      ) ||
      setweight(
        to_tsvector('russian',
          strip_html(coalesce(p.description, ''))
        ),
        'C'
      )
  WHERE p.oid = pid;
$$;
"""

_TRG_PRODUCTS_FN_SQL = """
CREATE OR REPLACE FUNCTION trg_products_search_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM refresh_product_search(NEW.oid);
  RETURN NULL;
END;
$$;
"""

# product_tags is the link table — INSERT attaches a tag, DELETE
# detaches one. UPDATE on it is unused today (rows are replaced via
# DELETE+INSERT in the PUT-style endpoint) but listing it would be
# defensive and harmless; skipped to keep the trigger surface small.
_TRG_PRODUCT_TAGS_FN_SQL = """
CREATE OR REPLACE FUNCTION trg_product_tags_search_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    PERFORM refresh_product_search(OLD.product_id);
  ELSE
    PERFORM refresh_product_search(NEW.product_id);
  END IF;
  RETURN NULL;
END;
$$;
"""

# Renaming a tag fans out to every product that carries it — one
# UPDATE per row. Tag renames are rare (admin-grade action); the
# cost is acceptable. If a tag is renamed on a catalog with N
# products carrying it, the originating PUT spends ~N×refresh time
# but it's atomic with the rename itself.
_TRG_TAGS_FN_SQL = """
CREATE OR REPLACE FUNCTION trg_tags_name_search_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM refresh_product_search(pt.product_id)
  FROM product_tags pt WHERE pt.tag_id = NEW.oid;
  RETURN NULL;
END;
$$;
"""

# Author rename fans out to every product the author owns. Same
# cost story as the tag rename trigger.
_TRG_USERS_FN_SQL = """
CREATE OR REPLACE FUNCTION trg_users_name_search_refresh()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  PERFORM refresh_product_search(p.oid)
  FROM products p WHERE p.author_id = NEW.oid;
  RETURN NULL;
END;
$$;
"""


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "products",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("search_text", sa.Text(), nullable=True),
    )

    op.execute(_STRIP_HTML_FN_SQL)
    op.execute(_REFRESH_FN_SQL)

    op.execute(_TRG_PRODUCTS_FN_SQL)
    op.execute(
        """
        CREATE TRIGGER trg_products_search
          AFTER INSERT OR UPDATE OF name, description, author_id
          ON products
          FOR EACH ROW
          EXECUTE FUNCTION trg_products_search_refresh();
        """,
    )

    op.execute(_TRG_PRODUCT_TAGS_FN_SQL)
    op.execute(
        """
        CREATE TRIGGER trg_product_tags_search
          AFTER INSERT OR DELETE ON product_tags
          FOR EACH ROW
          EXECUTE FUNCTION trg_product_tags_search_refresh();
        """,
    )

    op.execute(_TRG_TAGS_FN_SQL)
    op.execute(
        """
        CREATE TRIGGER trg_tags_name_search
          AFTER UPDATE OF name ON tags
          FOR EACH ROW
          EXECUTE FUNCTION trg_tags_name_search_refresh();
        """,
    )

    op.execute(_TRG_USERS_FN_SQL)
    op.execute(
        """
        CREATE TRIGGER trg_users_name_search
          AFTER UPDATE OF first_name, last_name, patronymic ON users
          FOR EACH ROW
          EXECUTE FUNCTION trg_users_name_search_refresh();
        """,
    )

    op.create_index(
        "ix_products_search_vector",
        "products",
        ["search_vector"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_products_search_text_trgm",
        "products",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    # Backfill — calls the helper once per existing row. Fine for
    # the current catalog size; rewrite as one bulk UPDATE with
    # joined aggregates if this table grows past ~100k rows.
    op.execute("SELECT refresh_product_search(oid) FROM products")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_users_name_search ON users")
    op.execute("DROP TRIGGER IF EXISTS trg_tags_name_search ON tags")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_product_tags_search ON product_tags",
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_products_search ON products",
    )
    op.execute(
        "DROP FUNCTION IF EXISTS trg_users_name_search_refresh()",
    )
    op.execute(
        "DROP FUNCTION IF EXISTS trg_tags_name_search_refresh()",
    )
    op.execute(
        "DROP FUNCTION IF EXISTS trg_product_tags_search_refresh()",
    )
    op.execute(
        "DROP FUNCTION IF EXISTS trg_products_search_refresh()",
    )
    op.execute(
        "DROP FUNCTION IF EXISTS refresh_product_search(uuid)",
    )
    op.execute("DROP FUNCTION IF EXISTS strip_html(text)")
    op.drop_index(
        "ix_products_search_text_trgm", table_name="products",
    )
    op.drop_index(
        "ix_products_search_vector", table_name="products",
    )
    op.drop_column("products", "search_text")
    op.drop_column("products", "search_vector")
    # Intentionally do NOT drop the pg_trgm extension here — other
    # features may start to depend on it independently of this
    # migration.
