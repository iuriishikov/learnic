"""SA tables for note releases — entity + 6 snapshot mirror tables.

Only the ``note_releases`` parent is mapped imperatively to a
domain entity (:class:`NoteRelease`). The six snapshot tables
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

from learnic.entities.note_block.constants import (
    BLOCK_TITLE_MAX_LEN,
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    PHOTO_COLLAGE_CAPTION_MAX_LEN,
    RUTUBE_VIDEO_ID_LENGTH,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_lesson.constants import LESSON_TITLE_MAX_LEN
from learnic.entities.note_module.constants import (
    MODULE_DESCRIPTION_MAX_LEN,
    MODULE_TITLE_MAX_LEN,
)
from learnic.entities.note_release.constants import RELEASE_NOTES_MAX_LEN
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.note_release.value_objects import (
    NoteReleaseVersion,
    ReleaseNotes,
)
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


note_releases_table = sa.Table(
    "note_releases",
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
            NoteReleaseKind,
            name="note_release_kind",
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
        name="uq_note_releases_product_ordinal",
    ),
    sa.UniqueConstraint(
        "product_id",
        "major",
        "minor",
        "patch",
        name="uq_note_releases_product_version",
    ),
    sa.Index(
        "ix_note_releases_product_ordinal_desc",
        "product_id",
        sa.text("ordinal DESC"),
    ),
)


# -------- snapshot mirror tables (Core only, no entity mapping) -------- #


note_release_modules_table = sa.Table(
    "note_release_modules",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("note_releases.oid", ondelete="CASCADE"),
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
        "ix_note_release_modules_release_position",
        "release_id",
        "position",
    ),
)


note_release_lessons_table = sa.Table(
    "note_release_lessons",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("note_releases.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "release_module_id",
        sa.Uuid,
        sa.ForeignKey("note_release_modules.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("source_lesson_id", sa.Uuid, nullable=True),
    sa.Column("title", sa.String(LESSON_TITLE_MAX_LEN), nullable=False),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Index(
        "ix_note_release_lessons_module_position",
        "release_module_id",
        "position",
    ),
    sa.Index(
        "ix_note_release_lessons_release_id",
        "release_id",
    ),
)


note_release_blocks_table = sa.Table(
    "note_release_blocks",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "release_id",
        sa.Uuid,
        sa.ForeignKey("note_releases.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "release_lesson_id",
        sa.Uuid,
        sa.ForeignKey("note_release_lessons.oid", ondelete="CASCADE"),
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
        "ix_note_release_blocks_lesson_position",
        "release_lesson_id",
        "position",
    ),
    sa.Index(
        "ix_note_release_blocks_release_id",
        "release_id",
    ),
)


note_release_html_blocks_table = sa.Table(
    "note_release_html_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("html", sa.String(HTML_BLOCK_MAX_LEN), nullable=False),
)


note_release_katex_blocks_table = sa.Table(
    "note_release_katex_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("source", sa.String(KATEX_BLOCK_MAX_LEN), nullable=False),
)


note_release_rutube_video_blocks_table = sa.Table(
    "note_release_rutube_video_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
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


note_release_code_blocks_table = sa.Table(
    "note_release_code_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("tabs", JSONB, nullable=False),
)


note_release_function_graph_blocks_table = sa.Table(
    "note_release_function_graph_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("config", JSONB, nullable=False),
)


# Snapshot mirrors of the draft choice / text-input subtype tables —
# same shapes, FK rebased to ``note_release_blocks``.
note_release_single_choice_blocks_table = sa.Table(
    "note_release_single_choice_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("options", JSONB, nullable=False),
    sa.Column("correct_option_id", sa.Uuid, nullable=False),
)


note_release_multi_choice_blocks_table = sa.Table(
    "note_release_multi_choice_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("options", JSONB, nullable=False),
    sa.Column("correct_option_ids", JSONB, nullable=False),
)


note_release_text_input_blocks_table = sa.Table(
    "note_release_text_input_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("accepted_answers", JSONB, nullable=False),
    sa.Column(
        "case_sensitive",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    ),
    sa.Column(
        "trim_whitespace",
        sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    ),
)


# Snapshot mirrors of the file-backed draft subtype tables. ``file_id``
# stays ``ON DELETE SET NULL`` on the release side too: a published
# release that referenced a now-deleted file degrades to a missing-file
# placeholder on read rather than failing to load.
note_release_file_blocks_table = sa.Table(
    "note_release_file_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "title",
        sa.String(BLOCK_TITLE_MAX_LEN),
        nullable=True,
    ),
)


note_release_video_file_blocks_table = sa.Table(
    "note_release_video_file_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "title",
        sa.String(BLOCK_TITLE_MAX_LEN),
        nullable=True,
    ),
)


note_release_photo_collage_blocks_table = sa.Table(
    "note_release_photo_collage_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("note_release_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "title",
        sa.String(BLOCK_TITLE_MAX_LEN),
        nullable=True,
    ),
)


# Snapshot mirror of the draft ``photo_collage_items`` child table.
# A published release used to denormalise items into a JSONB column on
# the block; they now live as rows so reads, the release-pin probe and
# storage-usage accounting are plain joins, symmetric with the draft
# side. ``oid`` is a fresh per-release surrogate PK — release tables
# never reuse draft ids — and ``source_item_id`` carries the draft item
# id so the reader can expose the same item identity the JSONB did.
# ``file_id`` stays ``ON DELETE SET NULL`` like the other file-backed
# release mirrors: a deleted file degrades to a placeholder, not a
# failed read.
note_release_photo_collage_items_table = sa.Table(
    "note_release_photo_collage_items",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "block_id",
        sa.Uuid,
        sa.ForeignKey(
            "note_release_photo_collage_blocks.oid",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    ),
    sa.Column("source_item_id", sa.Uuid, nullable=True),
    sa.Column("position", sa.Integer(), nullable=False),
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="SET NULL"),
        nullable=True,
    ),
    sa.Column(
        "caption",
        sa.String(PHOTO_COLLAGE_CAPTION_MAX_LEN),
        nullable=True,
    ),
    sa.UniqueConstraint(
        "block_id",
        "position",
        name="uq_note_release_photo_collage_items_block_position",
    ),
)


_release_mapped = False


def map_note_release_table() -> None:
    """Apply imperative mapping from :class:`NoteRelease`."""
    global _release_mapped  # noqa: PLW0603
    if _release_mapped:
        return
    mapper_registry.map_imperatively(
        NoteRelease,
        note_releases_table,
        properties={
            "oid": note_releases_table.c.oid,
            "product_id": note_releases_table.c.product_id,
            "ordinal": note_releases_table.c.ordinal,
            "version": composite(
                NoteReleaseVersion,
                note_releases_table.c.major,
                note_releases_table.c.minor,
                note_releases_table.c.patch,
            ),
            "kind": note_releases_table.c.kind,
            "notes": composite(
                ReleaseNotes.of_optional,
                note_releases_table.c.notes,
            ),
            "released_at": note_releases_table.c.released_at,
            "released_by": note_releases_table.c.released_by,
        },
        column_prefix="_col_",
    )
    _release_mapped = True
