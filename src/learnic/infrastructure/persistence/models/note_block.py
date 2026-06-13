"""SA Core tables for lesson blocks (joined inheritance, no mapper).

Lesson blocks use joined-inheritance: a ``lesson_blocks`` parent
table plus one child table per block type (``html_blocks``,
``katex_blocks``, ``rutube_video_blocks``). Because SQLAlchemy
imperative mapping doesn't play nicely with multi-table INSERT
semantics, blocks are NOT mapped to entity classes — the gateway
adapter works via Core ``insert``/``update``/``select`` statements
directly. This is an intentional, scoped exception to the
"imperative mapping per aggregate" convention used elsewhere in
this project.

Provider-specific embeds live in their own child table (Rutube
today, more later if needed) rather than a unified ``video_blocks``
table — id formats and embed contracts diverge per provider, and
a single table would force a fake abstraction.
"""

from enum import StrEnum

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB

from learnic.entities.note_block.constants import (
    BLOCK_TITLE_MAX_LEN,
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    PHOTO_COLLAGE_CAPTION_MAX_LEN,
    RUTUBE_VIDEO_ID_LENGTH,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.note_block.enums import BlockType
from learnic.infrastructure.persistence.models.registry import mapper_registry


def _enum_values(enum_cls: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_cls]


lesson_blocks_table = sa.Table(
    "lesson_blocks",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "lesson_id",
        sa.Uuid,
        sa.ForeignKey("note_lessons.oid", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column(
        "product_id",
        sa.Uuid,
        sa.ForeignKey("products.oid", ondelete="CASCADE"),
        nullable=False,
    ),
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
        "ix_lesson_blocks_lesson_position",
        "lesson_id",
        "position",
    ),
    sa.Index("ix_lesson_blocks_product_id", "product_id"),
)


html_blocks_table = sa.Table(
    "html_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "html",
        sa.String(HTML_BLOCK_MAX_LEN),
        nullable=False,
    ),
)


katex_blocks_table = sa.Table(
    "katex_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "source",
        sa.String(KATEX_BLOCK_MAX_LEN),
        nullable=False,
    ),
)


rutube_video_blocks_table = sa.Table(
    "rutube_video_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
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


code_blocks_table = sa.Table(
    "code_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    # ``tabs`` is a JSONB array of ``{"label": str, "source": str,
    # "language": str}`` objects. Stored opaque — the application layer
    # never queries inside it, so a denormalized column beats a child
    # table here. Length / count invariants are enforced upstream by
    # :class:`CodeBlock`'s ``__post_init__`` so the DB stores trusted data.
    sa.Column(
        "tabs",
        JSONB,
        nullable=False,
    ),
)


# ``config`` is the whole function-graph spec as one JSONB object
# (functions / curves / points / parameter sliders / viewport / axes).
# Stored opaque — the application never queries inside it; structural
# and expression-safety invariants are enforced upstream by
# :class:`GraphConfig`'s ``__post_init__`` so the DB stores trusted data.
function_graph_blocks_table = sa.Table(
    "function_graph_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "config",
        JSONB,
        nullable=False,
    ),
)


# ``options`` for both choice subtypes is a JSONB array of
# ``{"oid": "<uuid>", "label": "<str>"}`` objects — same denormalized
# rationale as ``code_blocks.tabs`` (opaque to SQL, invariants enforced
# upstream by the domain entity). For single-choice the correct id is
# a plain UUID column; for multi-choice it's a JSONB string-array so
# we don't fight asyncpg's UUID[] adapter for a payload that's never
# queried by element.
single_choice_blocks_table = sa.Table(
    "single_choice_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("options", JSONB, nullable=False),
    sa.Column("correct_option_id", sa.Uuid, nullable=False),
)


multi_choice_blocks_table = sa.Table(
    "multi_choice_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("options", JSONB, nullable=False),
    sa.Column("correct_option_ids", JSONB, nullable=False),
)


text_input_blocks_table = sa.Table(
    "text_input_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    # JSONB array of raw author-provided answer strings. Stored
    # verbatim; normalisation happens at check-time on the entity.
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


# File-backed block tables. ``file_id`` is ``ON DELETE CASCADE`` so
# enforcement of the storage quota (or any other hard-delete of the
# backing file) takes the block with it — product policy: if the
# author lost the file because they exceeded the quota and the grace
# period expired, the dependent block is no longer useful and goes
# too. Replace flows (update_file / update_video_file) UPDATE the
# block to point at the new file BEFORE the cascade fires, so the
# CASCADE finds nothing to delete in that case.
file_blocks_table = sa.Table(
    "file_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="CASCADE"),
        nullable=True,
    ),
    sa.Column(
        "title",
        sa.String(BLOCK_TITLE_MAX_LEN),
        nullable=True,
    ),
)


video_file_blocks_table = sa.Table(
    "video_file_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "file_id",
        sa.Uuid,
        sa.ForeignKey("files.oid", ondelete="CASCADE"),
        nullable=True,
    ),
    sa.Column(
        "title",
        sa.String(BLOCK_TITLE_MAX_LEN),
        nullable=True,
    ),
)


# Photo-collage items moved out of a JSONB array on
# ``photo_collage_blocks`` into a dedicated child table so granular
# operations (add / remove / reorder / caption edit) can address one
# photo by its stable ``oid`` without rewriting the whole array.
# Per-item file FKs are now real ``files`` references with
# ``ON DELETE SET NULL`` (same rationale as the parent ``file_blocks``
# / ``video_file_blocks``: the gallery survives backing-file deletion
# with a placeholder slot). The release snapshot side continues to
# store items denormalised inside a JSONB column on
# ``note_release_photo_collage_blocks``.
photo_collage_blocks_table = sa.Table(
    "photo_collage_blocks",
    mapper_registry.metadata,
    sa.Column(
        "oid",
        sa.Uuid,
        sa.ForeignKey("lesson_blocks.oid", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "title",
        sa.String(BLOCK_TITLE_MAX_LEN),
        nullable=True,
    ),
)


photo_collage_items_table = sa.Table(
    "photo_collage_items",
    mapper_registry.metadata,
    sa.Column("oid", sa.Uuid, primary_key=True),
    sa.Column(
        "block_id",
        sa.Uuid,
        sa.ForeignKey("photo_collage_blocks.oid", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("position", sa.Integer, nullable=False),
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
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        server_onupdate=sa.func.now(),
        nullable=False,
    ),
    # DEFERRABLE so reorder UPDATEs that swap positions inside a
    # single CASE WHEN statement don't fail the per-row check —
    # the constraint is only validated at COMMIT, by which point
    # every row has its final position.
    sa.UniqueConstraint(
        "block_id",
        "position",
        name="uq_photo_collage_items_block_position",
        deferrable=True,
        initially="DEFERRED",
    ),
)
