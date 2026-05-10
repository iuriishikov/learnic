"""SA tables for course releases — entity + 6 snapshot mirror tables.

Only the ``course_releases`` parent is mapped imperatively to a
domain entity (:class:`CourseRelease`). The six snapshot tables
mirror the draft schema (modules / lessons / blocks + 3 child
block tables) but are never mapped — content reads go through
the Reader's Core SELECTs and writes go through the
Snapshotter adapter (multi-table INSERTs do not play nicely
with imperative mapping).
"""

from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import composite

from learnic.entities.course_block.constants import (
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    RUTUBE_VIDEO_ID_LENGTH,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.course_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.course_release.constants import RELEASE_NOTES_MAX_LEN
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.course_release.value_objects import (
    CourseReleaseVersion,
    ReleaseNotes,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


course_releases_table = sa.Table(
    "course_releases",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("ordinal", sa.Integer(), nullable=False),
    sa.Column("major", sa.Integer(), nullable=False),
    sa.Column("minor", sa.Integer(), nullable=False),
    sa.Column("patch", sa.Integer(), nullable=False),
    sa.Column(
        "kind",
        sa.Enum(
            CourseReleaseKind,
            name="course_release_kind",
            values_callable=_enum_values,
        ),
        nullable=False,
    ),
    sa.Column(
        "notes",
        sa.String(RELEASE_NOTES_MAX_LEN),
        nullable=True,
    ),
    sa.Column(
        "released_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "released_by",
        sa.Uuid,
        sa.ForeignKey("users.oid", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.UniqueConstraint(
        "product_id",
        "ordinal",
        name="uq_course_releases_product_ordinal",
    ),
    sa.UniqueConstraint(
        "product_id",
        "major",
        "minor",
        "patch",
        name="uq_course_releases_product_version",
    ),
    sa.Index(
        "ix_course_releases_product_ordinal_desc",
        "product_id",
        sa.text("ordinal DESC"),
    ),
)


# -------- snapshot mirror tables (Core only, no entity mapping) -------- #


course_release_modules_table = sa.Table(
    "course_release_modules",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("course_releases.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("source_module_id", sa.Uuid, nullable=True),
    sa.Column("title", sa.String(MODULE_TITLE_MAX_LEN), nullable=False),
    sa.Column(
        "description",
        sa.String(MODULE_DESCRIPTION_MAX_LEN),
        nullable=True,
    ),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Index(
        "ix_course_release_modules_release_position",
        "release_id",
        "position",
    ),
)


course_release_lessons_table = sa.Table(
    "course_release_lessons",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("course_releases.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "release_module_id",
        sa.Uuid,
        sa.ForeignKey("course_release_modules.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("source_lesson_id", sa.Uuid, nullable=True),
    sa.Column("title", sa.String(LESSON_TITLE_MAX_LEN), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Index(
        "ix_course_release_lessons_module_position",
        "release_module_id",
        "position",
    ),
    sa.Index(
        "ix_course_release_lessons_release_id",
        "release_id",
    ),
)


course_release_blocks_table = sa.Table(
    "course_release_blocks",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("course_releases.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "release_lesson_id",
        sa.Uuid,
        sa.ForeignKey("course_release_lessons.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("source_block_id", sa.Uuid, nullable=True),
    sa.Column(
        "type",
        sa.Enum(
            BlockType,
            name="lesson_block_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    ),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Index(
        "ix_course_release_blocks_lesson_position",
        "release_lesson_id",
        "position",
    ),
    sa.Index(
        "ix_course_release_blocks_release_id",
        "release_id",
    ),
)


course_release_html_blocks_table = sa.Table(
    "course_release_html_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("course_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("html", sa.String(HTML_BLOCK_MAX_LEN), nullable=False),
)


course_release_katex_blocks_table = sa.Table(
    "course_release_katex_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("course_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("source", sa.String(KATEX_BLOCK_MAX_LEN), nullable=False),
)


course_release_rutube_video_blocks_table = sa.Table(
    "course_release_rutube_video_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("course_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "external_id",
        sa.String(RUTUBE_VIDEO_ID_LENGTH),
        nullable=False,
    ),
    sa.Column(
        "title",
        sa.String(VIDEO_TITLE_MAX_LEN),
        nullable=True,
    ),
)


course_release_code_blocks_table = sa.Table(
    "course_release_code_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("course_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("tabs", JSONB, nullable=False),
)


_release_mapped = False


def map_course_release_table() -> None:
    """Apply imperative mapping from :class:`CourseRelease`."""
    global _release_mapped  # noqa: PLW0603
    if _release_mapped:
        return
    mapper_registry.map_imperatively(
        CourseRelease,
        course_releases_table,
        properties={
            "oid": course_releases_table.c.oid,
            "product_id": course_releases_table.c.product_id,
            "ordinal": course_releases_table.c.ordinal,
            "version": composite(
                CourseReleaseVersion,
                course_releases_table.c.major,
                course_releases_table.c.minor,
                course_releases_table.c.patch,
            ),
            "kind": course_releases_table.c.kind,
            "notes": composite(
                ReleaseNotes.of_optional,
                course_releases_table.c.notes,
            ),
            "released_at": course_releases_table.c.released_at,
            "released_by": course_releases_table.c.released_by,
        },
        column_prefix="_col_",
    )
    _release_mapped = True
