import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.note_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.note_lesson.value_objects import LessonTitle
from learnic.infrastructure.persistence.models.registry import mapper_registry

note_lessons_table = sa.Table(
    "note_lessons",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "module_id",
        sa.Uuid,
        sa.ForeignKey("note_modules.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "title",
        sa.String(LESSON_TITLE_MAX_LEN),
        nullable=False,
    ),
    sa.Column(
        "position",
        sa.Integer(),
        nullable=False,
        server_default=sa.text("0"),
    ),
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
    ),
    sa.Index(
        "ix_note_lessons_module_position",
        "module_id",
        "position",
    ),
    sa.Index("ix_note_lessons_product_id", "product_id"),
)


_lesson_mapped = False


def map_note_lesson_table() -> None:
    """Apply imperative mapping from :class:`NoteLesson`."""
    global _lesson_mapped  # noqa: PLW0603
    if _lesson_mapped:
        return
    mapper_registry.map_imperatively(
        NoteLesson,
        note_lessons_table,
        properties={
            "oid": note_lessons_table.c.oid,
            "module_id": note_lessons_table.c.module_id,
            "product_id": note_lessons_table.c.product_id,
            "title": composite(
                LessonTitle,
                note_lessons_table.c.title,
            ),
            "position": note_lessons_table.c.position,
            "created_at": note_lessons_table.c.created_at,
            "updated_at": note_lessons_table.c.updated_at,
        },
        column_prefix="_col_",
    )
    _lesson_mapped = True
