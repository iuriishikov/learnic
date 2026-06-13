"""rename touch-product triggers course_* -> note_*

``prodtouch0001`` created ``trg_touch_product_on_course_modules`` and
``trg_touch_product_on_course_lessons`` on the then-named
``course_modules`` / ``course_lessons`` tables. ``note0001`` later
renamed those tables to ``note_modules`` / ``note_lessons`` — and in
Postgres a trigger follows its table across ``ALTER TABLE ... RENAME``,
so the triggers kept firing but kept their stale ``course_*`` names.

This is cosmetic only (the trigger body is table-name-agnostic), but the
``course_*`` trigger name sitting on a ``note_*`` table misleads anyone
debugging by trigger name. Rename them to match. The ``lesson_blocks``
trigger is untouched — that table was never renamed.

Revision ID: trigrename0001
Revises: filefk0001
Create Date: 2026-06-13 00:02:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "trigrename0001"
down_revision: Union[str, Sequence[str], None] = "filefk0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TRIGGER trg_touch_product_on_course_modules ON note_modules "
        "RENAME TO trg_touch_product_on_note_modules",
    )
    op.execute(
        "ALTER TRIGGER trg_touch_product_on_course_lessons ON note_lessons "
        "RENAME TO trg_touch_product_on_note_lessons",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TRIGGER trg_touch_product_on_note_modules ON note_modules "
        "RENAME TO trg_touch_product_on_course_modules",
    )
    op.execute(
        "ALTER TRIGGER trg_touch_product_on_note_lessons ON note_lessons "
        "RENAME TO trg_touch_product_on_course_lessons",
    )
