"""Per-:class:`BlockType` spec registry for the persistence layer.

Centralises the four if/elif chains that previously had to be kept
in lock-step across the persistence adapters:

* :func:`_row_to_block` in ``adapters/course_block.py`` — row →
  ``LessonBlock`` entity (draft side).
* :func:`_row_to_block_view` in ``adapters/course_content.py`` —
  row → ``LessonBlockView`` (draft side).
* :func:`_row_to_block_view` in ``adapters/course_release.py`` —
  row → ``LessonBlockView`` (release / snapshot side).
* :func:`_partition_subtypes` in ``adapters/course_release.py`` —
  per-row routing of subtype INSERT payloads (release side).

Adding a new :class:`BlockType` variant is now a single new
:class:`BlockSpec` instance plus a new entry in :data:`BLOCK_SPECS`
— the four dispatch points read through this registry instead of
growing a fifth branch each.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Final

import sqlalchemy as sa

from learnic.application.common.persistence.course_content import (
    CodeBlockView,
    CodeTabView,
    HtmlBlockView,
    KatexBlockView,
    LessonBlockView,
    RutubeVideoBlockView,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import (
    CodeBlock,
    CodeTab,
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    RutubeVideoBlock,
)
from learnic.entities.course_block.value_objects import (
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.course_block import (
    code_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    rutube_video_blocks_table,
)
from learnic.infrastructure.persistence.models.course_release import (
    course_release_code_blocks_table,
    course_release_html_blocks_table,
    course_release_katex_blocks_table,
    course_release_rutube_video_blocks_table,
)


@dataclass(slots=True, frozen=True)
class _CommonBlockAttrs:
    """Parent-row attributes shared by every block type."""

    oid: LessonBlockID
    lesson_id: CourseLessonID
    product_id: ProductID
    position: int
    created_at: Any
    updated_at: Any


def _common_from_row(row: sa.Row[Any]) -> _CommonBlockAttrs:
    return _CommonBlockAttrs(
        oid=LessonBlockID(row.oid),
        lesson_id=CourseLessonID(row.lesson_id),
        product_id=ProductID(row.product_id),
        position=row.position,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _jsonb_to_tab_views(raw: Any) -> list[CodeTabView]:
    return [
        CodeTabView(
            label=item["label"],
            source=item["source"],
            language=item["language"],
        )
        for item in raw
    ]


def _jsonb_to_tabs(raw: Any) -> list[CodeTab]:
    return [
        CodeTab(
            label=CodeTabLabel(item["label"]),
            source=CodeSource(item["source"]),
            language=CodeLanguage(item["language"]),
        )
        for item in raw
    ]


@dataclass(slots=True, frozen=True)
class BlockSpec:
    """Everything the persistence layer needs to know about one block type.

    Attributes:
        kind: The :class:`BlockType` discriminator.
        draft_subtype_table: Child table holding type-specific
            columns for draft blocks (e.g. ``html_blocks``).
        release_subtype_table: Mirror table on the snapshot side
            (e.g. ``course_release_html_blocks``).
        row_to_entity: Build a domain :class:`LessonBlock` from a
            row joined across the parent + subtype tables.
        row_to_view: Build a read-side ``LessonBlockView`` from a
            row joined across the parent + subtype tables. Works on
            both the draft and the release selects because both
            select the subtype columns under the same labels.
        release_insert_value: Build the per-row INSERT payload for
            the release subtype table (``oid`` plus subtype-specific
            columns).
    """

    kind: BlockType
    draft_subtype_table: sa.Table
    release_subtype_table: sa.Table
    row_to_entity: Callable[[sa.Row[Any], _CommonBlockAttrs], LessonBlock]
    row_to_view: Callable[[sa.Row[Any]], LessonBlockView]
    release_insert_value: Callable[[sa.Row[Any], Any], dict[str, Any]]


# ============================== HTML ============================== #


def _html_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> HtmlBlock:
    return HtmlBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        html=HtmlContent(row.html),
    )


def _html_row_to_view(row: sa.Row[Any]) -> HtmlBlockView:
    return HtmlBlockView(
        type=BlockType.HTML,
        oid=LessonBlockID(row.oid),
        position=row.position,
        html=row.html,
    )


def _html_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {"oid": new_oid, "html": row.html}


# ============================== KaTeX ============================== #


def _katex_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> KatexBlock:
    return KatexBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        source=KatexSource(row.source),
    )


def _katex_row_to_view(row: sa.Row[Any]) -> KatexBlockView:
    return KatexBlockView(
        type=BlockType.KATEX,
        oid=LessonBlockID(row.oid),
        position=row.position,
        source=row.source,
    )


def _katex_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {"oid": new_oid, "source": row.source}


# ============================== Rutube ============================== #


def _rutube_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> RutubeVideoBlock:
    return RutubeVideoBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        external_id=RutubeVideoID(row.rutube_external_id),
        title=(VideoTitle(row.rutube_title) if row.rutube_title is not None else None),
    )


def _rutube_row_to_view(row: sa.Row[Any]) -> RutubeVideoBlockView:
    return RutubeVideoBlockView(
        type=BlockType.RUTUBE_VIDEO,
        oid=LessonBlockID(row.oid),
        position=row.position,
        external_id=row.rutube_external_id,
        title=row.rutube_title,
    )


def _rutube_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "external_id": row.rutube_external_id,
        "title": row.rutube_title,
    }


# ============================== Code ============================== #


def _code_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> CodeBlock:
    return CodeBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        tabs=_jsonb_to_tabs(row.code_tabs),
    )


def _code_row_to_view(row: sa.Row[Any]) -> CodeBlockView:
    return CodeBlockView(
        type=BlockType.CODE,
        oid=LessonBlockID(row.oid),
        position=row.position,
        tabs=_jsonb_to_tab_views(row.code_tabs),
    )


def _code_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    # Snapshots take the JSONB tabs payload as-is — release content
    # is immutable so a deep copy isn't required (psycopg/asyncpg
    # encodes the dict to JSON on insert independently per row).
    return {"oid": new_oid, "tabs": row.code_tabs}


# ============================== Registry ============================== #


BLOCK_SPECS: Final[dict[BlockType, BlockSpec]] = {
    BlockType.HTML: BlockSpec(
        kind=BlockType.HTML,
        draft_subtype_table=html_blocks_table,
        release_subtype_table=course_release_html_blocks_table,
        row_to_entity=_html_row_to_entity,
        row_to_view=_html_row_to_view,
        release_insert_value=_html_release_insert_value,
    ),
    BlockType.KATEX: BlockSpec(
        kind=BlockType.KATEX,
        draft_subtype_table=katex_blocks_table,
        release_subtype_table=course_release_katex_blocks_table,
        row_to_entity=_katex_row_to_entity,
        row_to_view=_katex_row_to_view,
        release_insert_value=_katex_release_insert_value,
    ),
    BlockType.RUTUBE_VIDEO: BlockSpec(
        kind=BlockType.RUTUBE_VIDEO,
        draft_subtype_table=rutube_video_blocks_table,
        release_subtype_table=course_release_rutube_video_blocks_table,
        row_to_entity=_rutube_row_to_entity,
        row_to_view=_rutube_row_to_view,
        release_insert_value=_rutube_release_insert_value,
    ),
    BlockType.CODE: BlockSpec(
        kind=BlockType.CODE,
        draft_subtype_table=code_blocks_table,
        release_subtype_table=course_release_code_blocks_table,
        row_to_entity=_code_row_to_entity,
        row_to_view=_code_row_to_view,
        release_insert_value=_code_release_insert_value,
    ),
}


# Fail-fast: every BlockType variant must have a spec.
_missing = set(BlockType) - set(BLOCK_SPECS)
if _missing:
    raise RuntimeError(
        "BLOCK_SPECS is incomplete; missing entries for: "
        f"{sorted(b.value for b in _missing)}",
    )


def spec_for(kind: BlockType) -> BlockSpec:
    """Return the spec for ``kind``."""
    return BLOCK_SPECS[kind]


def spec_for_row(row: sa.Row[Any]) -> BlockSpec:
    """Resolve ``row.type`` to its spec.

    ``row.type`` may arrive as either a :class:`BlockType` enum (after
    SA's enum decoding) or a raw string (in certain release queries
    that read it untyped). Normalise here so callers don't repeat the
    coercion.
    """
    raw = row.type
    block_type = raw if isinstance(raw, BlockType) else BlockType(raw)
    return BLOCK_SPECS[block_type]
