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

from learnic.entities.course_block.constants import (
    HTML_BLOCK_MAX_LEN,
    KATEX_BLOCK_MAX_LEN,
    RUTUBE_VIDEO_ID_LENGTH,
    VIDEO_TITLE_MAX_LEN,
)
from learnic.entities.course_block.enums import BlockType
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
        sa.ForeignKey("course_lessons.oid", ondelete="CASCADE"),
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
