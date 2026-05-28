"""bump products.updated_at on any course-content change

The ``products.updated_at`` column only moves when the ``products`` row
itself is written, but course content lives in ``course_modules`` /
``course_lessons`` / ``lesson_blocks``. Editing content therefore left
the product's "updated N ago" label frozen.

This adds a trigger function plus AFTER INSERT/UPDATE/DELETE triggers on
those three tables — all of which carry a denormalised ``product_id`` —
so any content mutation touches the parent product's ``updated_at``.
Block content edits (every ``update_*`` adapter method, including photo
collage items via ``_touch_collage_parent``) already write the parent
``lesson_blocks`` row, so a single trigger on ``lesson_blocks`` covers
every block-level edit; module/lesson edits are covered by the triggers
on their own tables. No application-handler changes are needed, and
future content operations are covered automatically.

Revision ID: prodtouch0001
Revises: stat0002
Create Date: 2026-05-26 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "prodtouch0001"
down_revision: Union[str, Sequence[str], None] = "stat0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CONTENT_TABLES = ("course_modules", "course_lessons", "lesson_blocks")


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION touch_product_updated_at()
        RETURNS trigger AS $$
        BEGIN
            UPDATE products
               SET updated_at = now()
             WHERE oid = COALESCE(NEW.product_id, OLD.product_id);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """,
    )
    for table in _CONTENT_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_touch_product_on_{table}
            AFTER INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION touch_product_updated_at();
            """,
        )


def downgrade() -> None:
    for table in _CONTENT_TABLES:
        op.execute(
            f"DROP TRIGGER IF EXISTS trg_touch_product_on_{table} ON {table};",
        )
    op.execute("DROP FUNCTION IF EXISTS touch_product_updated_at();")
