"""rename course → note (tables, indexes, constraints, enum type & values)

Full rebrand of the "course" concept to "note" (UI: «конспект»).

Renames, all metadata-only (no row rewrites):

* the 16 ``course_*`` content/release tables + ``enrollment_course_details``;
* every index / unique / PK / FK constraint left on those tables after the
  table rename — including the Postgres auto-named ``*_fkey`` / ``*_pkey``
  ones whose names are generated at runtime and therefore not knowable from
  the migration sources (handled by a sweep scoped strictly to these tables);
* the ``course_release_kind`` enum *type* → ``note_release_kind``;
* the ``'course'`` *value* of the ``product_type`` and ``enrollment_kind``
  enums → ``'note'`` (PG 10+ ``ALTER TYPE … RENAME VALUE`` is in-place).

Intentionally excluded:

* ``course_enrollments`` and its objects — dropped by ``aa1b8cde7f01``
  (unify_enrollments); no longer present in the live schema.
* ``course_release_latex_blocks`` — already renamed to ``…katex…`` by
  ``d4a8f7c12e90``; the katex table is covered below.

No columns are renamed: the only ``course_*`` identifiers outside table /
constraint names were SQLAlchemy ``.label()`` aliases in the enrollment
adapter (Python-internal), not DB columns.

Revision ID: note0001
Revises: blog0001
Create Date: 2026-06-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


revision: str = "note0001"
down_revision: Union[str, Sequence[str], None] = "blog0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (old_name, new_name). Order is irrelevant for pure renames — rename_table
# does not touch FK targets, and the schema is internally consistent before
# and after.
_TABLES: list[tuple[str, str]] = [
    ("course_releases", "note_releases"),
    ("course_modules", "note_modules"),
    ("course_lessons", "note_lessons"),
    ("course_release_modules", "note_release_modules"),
    ("course_release_lessons", "note_release_lessons"),
    ("course_release_blocks", "note_release_blocks"),
    ("course_release_html_blocks", "note_release_html_blocks"),
    ("course_release_katex_blocks", "note_release_katex_blocks"),
    ("course_release_rutube_video_blocks", "note_release_rutube_video_blocks"),
    ("course_release_code_blocks", "note_release_code_blocks"),
    ("course_release_single_choice_blocks", "note_release_single_choice_blocks"),
    ("course_release_multi_choice_blocks", "note_release_multi_choice_blocks"),
    ("course_release_text_input_blocks", "note_release_text_input_blocks"),
    ("course_release_file_blocks", "note_release_file_blocks"),
    ("course_release_video_file_blocks", "note_release_video_file_blocks"),
    ("course_release_photo_collage_blocks", "note_release_photo_collage_blocks"),
    ("enrollment_course_details", "enrollment_note_details"),
]


def _rename_objects(tables: Sequence[str], frm: str, to: str) -> None:
    """Rename every constraint then index on ``tables`` whose name contains
    ``frm``, replacing the first occurrence of ``frm`` with ``to``.

    Scoped strictly to ``tables`` so it can never rename an unrelated object
    (e.g. an index on the ``notes`` column). Constraints are renamed *before*
    plain indexes because ``ALTER TABLE … RENAME CONSTRAINT`` also renames the
    unique/PK constraint's backing index — doing indexes first would clash.
    """
    tables_sql = ", ".join(f"'{t}'" for t in tables)
    op.execute(
        f"""
        DO $$
        DECLARE
            r record;
        BEGIN
            -- constraints first (FK / UNIQUE / PK / CHECK); this also renames
            -- the backing index of UNIQUE/PK constraints.
            FOR r IN
                SELECT con.conname AS name, c.relname AS tbl
                FROM pg_constraint con
                JOIN pg_class c ON c.oid = con.conrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ({tables_sql})
                  AND con.conname LIKE '%{frm}%'
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I RENAME CONSTRAINT %I TO %I',
                    r.tbl, r.name, regexp_replace(r.name, '{frm}', '{to}')
                );
            END LOOP;
            -- remaining plain (non-constraint) indexes
            FOR r IN
                SELECT i.relname AS name
                FROM pg_index x
                JOIN pg_class i ON i.oid = x.indexrelid
                JOIN pg_class c ON c.oid = x.indrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public'
                  AND c.relname IN ({tables_sql})
                  AND i.relname LIKE '%{frm}%'
            LOOP
                EXECUTE format(
                    'ALTER INDEX %I RENAME TO %I',
                    r.name, regexp_replace(r.name, '{frm}', '{to}')
                );
            END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    """Upgrade schema."""
    for old, new in _TABLES:
        op.rename_table(old, new)
    _rename_objects([new for _, new in _TABLES], "course", "note")
    op.execute("ALTER TYPE course_release_kind RENAME TO note_release_kind")
    op.execute("ALTER TYPE product_type RENAME VALUE 'course' TO 'note'")
    op.execute("ALTER TYPE enrollment_kind RENAME VALUE 'course' TO 'note'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TYPE enrollment_kind RENAME VALUE 'note' TO 'course'")
    op.execute("ALTER TYPE product_type RENAME VALUE 'note' TO 'course'")
    op.execute("ALTER TYPE note_release_kind RENAME TO course_release_kind")
    for old, new in _TABLES:
        op.rename_table(new, old)
    _rename_objects([old for old, _ in _TABLES], "note", "course")
