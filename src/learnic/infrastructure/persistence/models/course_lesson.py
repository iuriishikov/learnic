import sqlalchemy as sa
from sqlalchemy.orm import composite

from learnic.entities.course_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_lesson.value_objects import LessonTitle
from learnic.infrastructure.persistence.models.registry import mapper_registry

course_lessons_table = sa.Table(
    "course_lessons",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "module_id",
        sa.Uuid,
        sa.ForeignKey("course_modules.oid", ondelete="CASCADE"),
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
        "ix_course_lessons_module_position",
        "module_id",
        "position",
    ),
    sa.Index("ix_course_lessons_product_id", "product_id"),
)


_lesson_mapped = False


def map_course_lesson_table() -> None:
    """Apply imperative mapping from :class:`CourseLesson`."""
    global _lesson_mapped  # noqa: PLW0603
    if _lesson_mapped:
        return
    mapper_registry.map_imperatively(
        CourseLesson,
        course_lessons_table,
        properties={
            "oid": course_lessons_table.c.oid,
            "module_id": course_lessons_table.c.module_id,
            "product_id": course_lessons_table.c.product_id,
            "title": composite(
                LessonTitle,
                course_lessons_table.c.title,
            ),
            "position": course_lessons_table.c.position,
            "created_at": course_lessons_table.c.created_at,
            "updated_at": course_lessons_table.c.updated_at,
        },
        column_prefix="_col_",
    )
    _lesson_mapped = True
