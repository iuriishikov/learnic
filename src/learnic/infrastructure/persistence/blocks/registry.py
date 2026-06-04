"""Per-:class:`BlockType` spec registry for the persistence layer.

Centralises the four if/elif chains that previously had to be kept
in lock-step across the persistence adapters:

* :func:`_row_to_block` in ``adapters/note_block.py`` — row →
  ``LessonBlock`` entity (draft side).
* :func:`_row_to_block_view` in ``adapters/note_content.py`` —
  row → ``LessonBlockView`` (draft side).
* :func:`_row_to_block_view` in ``adapters/note_release.py`` —
  row → ``LessonBlockView`` (release / snapshot side).
* :func:`_partition_subtypes` in ``adapters/note_release.py`` —
  per-row routing of subtype INSERT payloads (release side).

Adding a new :class:`BlockType` variant is now a single new
:class:`BlockSpec` instance plus a new entry in :data:`BLOCK_SPECS`
— the four dispatch points read through this registry instead of
growing a fifth branch each.
"""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

import sqlalchemy as sa

from learnic.application.common.persistence.note_content import (
    ChoiceOptionView,
    CodeBlockView,
    CodeTabView,
    CollageItemView,
    FileBlockView,
    HtmlBlockView,
    KatexBlockView,
    LessonBlockView,
    MultiChoiceBlockView,
    PhotoCollageBlockView,
    RutubeVideoBlockView,
    SingleChoiceBlockView,
    TextInputBlockView,
    VideoFileBlockView,
)
from learnic.application.common.persistence.file import FileView
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import (
    ChoiceOptionID,
    CollageItemID,
    LessonBlockID,
)
from learnic.entities.note_block.models import (
    ChoiceOption,
    CodeBlock,
    CodeTab,
    CollageItem,
    FileBlock,
    HtmlBlock,
    KatexBlock,
    LessonBlock,
    MultiChoiceBlock,
    PhotoCollageBlock,
    RutubeVideoBlock,
    SingleChoiceBlock,
    TextInputBlock,
    VideoFileBlock,
)
from learnic.entities.note_block.value_objects import (
    AcceptedAnswer,
    BlockTitle,
    ChoiceOptionLabel,
    CodeLanguage,
    CodeSource,
    CodeTabLabel,
    CollageCaption,
    HtmlContent,
    KatexSource,
    RutubeVideoID,
    VideoTitle,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.note_block import (
    code_blocks_table,
    file_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    multi_choice_blocks_table,
    photo_collage_blocks_table,
    rutube_video_blocks_table,
    single_choice_blocks_table,
    text_input_blocks_table,
    video_file_blocks_table,
)
from learnic.infrastructure.persistence.models.note_release import (
    note_release_code_blocks_table,
    note_release_file_blocks_table,
    note_release_html_blocks_table,
    note_release_katex_blocks_table,
    note_release_multi_choice_blocks_table,
    note_release_photo_collage_blocks_table,
    note_release_rutube_video_blocks_table,
    note_release_single_choice_blocks_table,
    note_release_text_input_blocks_table,
    note_release_video_file_blocks_table,
)


@dataclass(slots=True, frozen=True)
class _CommonBlockAttrs:
    """Parent-row attributes shared by every block type."""

    oid: LessonBlockID
    lesson_id: NoteLessonID
    product_id: ProductID
    position: int
    created_at: Any
    updated_at: Any


def _common_from_row(row: sa.Row[Any]) -> _CommonBlockAttrs:
    return _CommonBlockAttrs(
        oid=LessonBlockID(row.oid),
        lesson_id=NoteLessonID(row.lesson_id),
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


def _jsonb_to_option_views(raw: Any) -> list[ChoiceOptionView]:
    return [
        ChoiceOptionView(oid=item["oid"], label=item["label"]) for item in raw
    ]


def _jsonb_to_options(raw: Any) -> list[ChoiceOption]:
    return [
        ChoiceOption(
            oid=ChoiceOptionID(uuid.UUID(item["oid"])),
            label=ChoiceOptionLabel(item["label"]),
        )
        for item in raw
    ]


def _jsonb_to_correct_ids(raw: Any) -> frozenset[ChoiceOptionID]:
    return frozenset(ChoiceOptionID(uuid.UUID(s)) for s in raw)


def _jsonb_to_accepted_answers(raw: Any) -> list[AcceptedAnswer]:
    return [AcceptedAnswer(s) for s in raw]


@dataclass(slots=True, frozen=True)
class BlockSpec:
    """Everything the persistence layer needs to know about one block type.

    Attributes:
        kind: The :class:`BlockType` discriminator.
        draft_subtype_table: Child table holding type-specific
            columns for draft blocks (e.g. ``html_blocks``).
        release_subtype_table: Mirror table on the snapshot side
            (e.g. ``note_release_html_blocks``).
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
    row_to_view: Callable[
        [sa.Row[Any], Mapping[FileID, FileView]],
        LessonBlockView,
    ]
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


def _html_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> HtmlBlockView:
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


def _katex_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> KatexBlockView:
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


def _rutube_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> RutubeVideoBlockView:
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


def _code_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> CodeBlockView:
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


# ============================== Single Choice ============================== #


def _single_choice_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> SingleChoiceBlock:
    return SingleChoiceBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        options=_jsonb_to_options(row.single_choice_options),
        correct_option_id=ChoiceOptionID(row.single_choice_correct_option_id),
    )


def _single_choice_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> SingleChoiceBlockView:
    return SingleChoiceBlockView(
        type=BlockType.SINGLE_CHOICE,
        oid=LessonBlockID(row.oid),
        position=row.position,
        options=_jsonb_to_option_views(row.single_choice_options),
        correct_option_id=str(row.single_choice_correct_option_id),
    )


def _single_choice_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "options": row.single_choice_options,
        "correct_option_id": row.single_choice_correct_option_id,
    }


# ============================== Multi Choice ============================== #


def _multi_choice_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> MultiChoiceBlock:
    return MultiChoiceBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        options=_jsonb_to_options(row.multi_choice_options),
        correct_option_ids=_jsonb_to_correct_ids(
            row.multi_choice_correct_option_ids,
        ),
    )


def _multi_choice_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> MultiChoiceBlockView:
    return MultiChoiceBlockView(
        type=BlockType.MULTI_CHOICE,
        oid=LessonBlockID(row.oid),
        position=row.position,
        options=_jsonb_to_option_views(row.multi_choice_options),
        correct_option_ids=list(row.multi_choice_correct_option_ids),
    )


def _multi_choice_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "options": row.multi_choice_options,
        "correct_option_ids": row.multi_choice_correct_option_ids,
    }


# ============================== Text Input ============================== #


def _text_input_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> TextInputBlock:
    return TextInputBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        accepted_answers=_jsonb_to_accepted_answers(
            row.text_input_accepted_answers,
        ),
        case_sensitive=row.text_input_case_sensitive,
        trim_whitespace=row.text_input_trim_whitespace,
    )


def _text_input_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],  # noqa: ARG001 — file-less block type
) -> TextInputBlockView:
    return TextInputBlockView(
        type=BlockType.TEXT_INPUT,
        oid=LessonBlockID(row.oid),
        position=row.position,
        accepted_answers=list(row.text_input_accepted_answers),
        case_sensitive=row.text_input_case_sensitive,
        trim_whitespace=row.text_input_trim_whitespace,
    )


def _text_input_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "accepted_answers": row.text_input_accepted_answers,
        "case_sensitive": row.text_input_case_sensitive,
        "trim_whitespace": row.text_input_trim_whitespace,
    }


# ============================== File ============================== #


def _file_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> FileBlock:
    return FileBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        file_id=(
            FileID(row.file_block_file_id)
            if row.file_block_file_id is not None
            else None
        ),
        title=(
            BlockTitle(row.file_block_title)
            if row.file_block_title is not None
            else None
        ),
    )


def _file_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],
) -> FileBlockView:
    fid = row.file_block_file_id
    return FileBlockView(
        type=BlockType.FILE,
        oid=LessonBlockID(row.oid),
        position=row.position,
        file=files.get(FileID(fid)) if fid is not None else None,
        title=row.file_block_title,
    )


def _file_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "file_id": row.file_block_file_id,
        "title": row.file_block_title,
    }


# ============================== Video File ============================== #


def _video_file_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> VideoFileBlock:
    return VideoFileBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        file_id=(
            FileID(row.video_file_block_file_id)
            if row.video_file_block_file_id is not None
            else None
        ),
        title=(
            BlockTitle(row.video_file_block_title)
            if row.video_file_block_title is not None
            else None
        ),
    )


def _video_file_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],
) -> VideoFileBlockView:
    fid = row.video_file_block_file_id
    return VideoFileBlockView(
        type=BlockType.VIDEO_FILE,
        oid=LessonBlockID(row.oid),
        position=row.position,
        file=files.get(FileID(fid)) if fid is not None else None,
        title=row.video_file_block_title,
    )


def _video_file_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "file_id": row.video_file_block_file_id,
        "title": row.video_file_block_title,
    }


# ============================== Photo Collage ============================== #


def collage_items_payload_to_domain(raw: Any) -> list[CollageItem]:
    """Decode a list of item dicts into domain :class:`CollageItem`.

    Shape is the canonical ``{"oid", "file_id", "caption"}`` triple
    used in BOTH the release JSONB snapshot AND the draft-side
    composition assembled by :class:`NoteContentReaderAlchemy` /
    :class:`LessonBlockGatewayAlchemy` before dispatch (those callers
    re-shape rows from ``photo_collage_items_table`` into this dict
    form so the registry stays one code path across draft and
    release).
    """
    return [
        CollageItem(
            oid=CollageItemID(uuid.UUID(item["oid"])),
            file_id=FileID(uuid.UUID(item["file_id"]))
            if item.get("file_id") is not None
            else None,
            caption=CollageCaption(item["caption"])
            if item.get("caption") is not None
            else None,
        )
        for item in raw
    ]


def collage_items_payload_to_views(
    raw: Any,
    files: Mapping[FileID, FileView],
) -> list[CollageItemView]:
    items: list[CollageItemView] = []
    for item in raw:
        raw_fid = item.get("file_id")
        if raw_fid is not None:
            file_view = files.get(FileID(uuid.UUID(raw_fid)))
        else:
            file_view = None
        items.append(
            CollageItemView(
                oid=item["oid"],
                file=file_view,
                caption=item.get("caption"),
            ),
        )
    return items


def _photo_collage_row_to_entity(
    row: sa.Row[Any],
    common: _CommonBlockAttrs,
) -> PhotoCollageBlock:
    return PhotoCollageBlock(
        oid=common.oid,
        lesson_id=common.lesson_id,
        product_id=common.product_id,
        position=common.position,
        created_at=common.created_at,
        updated_at=common.updated_at,
        items=collage_items_payload_to_domain(row.photo_collage_items),
        title=(
            BlockTitle(row.photo_collage_title)
            if row.photo_collage_title is not None
            else None
        ),
    )


def _photo_collage_row_to_view(
    row: sa.Row[Any],
    files: Mapping[FileID, FileView],
) -> PhotoCollageBlockView:
    return PhotoCollageBlockView(
        type=BlockType.PHOTO_COLLAGE,
        oid=LessonBlockID(row.oid),
        position=row.position,
        items=collage_items_payload_to_views(row.photo_collage_items, files),
        title=row.photo_collage_title,
    )


def _photo_collage_release_insert_value(
    row: sa.Row[Any],
    new_oid: Any,
) -> dict[str, Any]:
    return {
        "oid": new_oid,
        "items": row.photo_collage_items,
        "title": row.photo_collage_title,
    }


# ============================== Registry ============================== #


BLOCK_SPECS: Final[dict[BlockType, BlockSpec]] = {
    BlockType.HTML: BlockSpec(
        kind=BlockType.HTML,
        draft_subtype_table=html_blocks_table,
        release_subtype_table=note_release_html_blocks_table,
        row_to_entity=_html_row_to_entity,
        row_to_view=_html_row_to_view,
        release_insert_value=_html_release_insert_value,
    ),
    BlockType.KATEX: BlockSpec(
        kind=BlockType.KATEX,
        draft_subtype_table=katex_blocks_table,
        release_subtype_table=note_release_katex_blocks_table,
        row_to_entity=_katex_row_to_entity,
        row_to_view=_katex_row_to_view,
        release_insert_value=_katex_release_insert_value,
    ),
    BlockType.RUTUBE_VIDEO: BlockSpec(
        kind=BlockType.RUTUBE_VIDEO,
        draft_subtype_table=rutube_video_blocks_table,
        release_subtype_table=note_release_rutube_video_blocks_table,
        row_to_entity=_rutube_row_to_entity,
        row_to_view=_rutube_row_to_view,
        release_insert_value=_rutube_release_insert_value,
    ),
    BlockType.CODE: BlockSpec(
        kind=BlockType.CODE,
        draft_subtype_table=code_blocks_table,
        release_subtype_table=note_release_code_blocks_table,
        row_to_entity=_code_row_to_entity,
        row_to_view=_code_row_to_view,
        release_insert_value=_code_release_insert_value,
    ),
    BlockType.SINGLE_CHOICE: BlockSpec(
        kind=BlockType.SINGLE_CHOICE,
        draft_subtype_table=single_choice_blocks_table,
        release_subtype_table=note_release_single_choice_blocks_table,
        row_to_entity=_single_choice_row_to_entity,
        row_to_view=_single_choice_row_to_view,
        release_insert_value=_single_choice_release_insert_value,
    ),
    BlockType.MULTI_CHOICE: BlockSpec(
        kind=BlockType.MULTI_CHOICE,
        draft_subtype_table=multi_choice_blocks_table,
        release_subtype_table=note_release_multi_choice_blocks_table,
        row_to_entity=_multi_choice_row_to_entity,
        row_to_view=_multi_choice_row_to_view,
        release_insert_value=_multi_choice_release_insert_value,
    ),
    BlockType.TEXT_INPUT: BlockSpec(
        kind=BlockType.TEXT_INPUT,
        draft_subtype_table=text_input_blocks_table,
        release_subtype_table=note_release_text_input_blocks_table,
        row_to_entity=_text_input_row_to_entity,
        row_to_view=_text_input_row_to_view,
        release_insert_value=_text_input_release_insert_value,
    ),
    BlockType.FILE: BlockSpec(
        kind=BlockType.FILE,
        draft_subtype_table=file_blocks_table,
        release_subtype_table=note_release_file_blocks_table,
        row_to_entity=_file_row_to_entity,
        row_to_view=_file_row_to_view,
        release_insert_value=_file_release_insert_value,
    ),
    BlockType.VIDEO_FILE: BlockSpec(
        kind=BlockType.VIDEO_FILE,
        draft_subtype_table=video_file_blocks_table,
        release_subtype_table=note_release_video_file_blocks_table,
        row_to_entity=_video_file_row_to_entity,
        row_to_view=_video_file_row_to_view,
        release_insert_value=_video_file_release_insert_value,
    ),
    BlockType.PHOTO_COLLAGE: BlockSpec(
        kind=BlockType.PHOTO_COLLAGE,
        draft_subtype_table=photo_collage_blocks_table,
        release_subtype_table=note_release_photo_collage_blocks_table,
        row_to_entity=_photo_collage_row_to_entity,
        row_to_view=_photo_collage_row_to_view,
        release_insert_value=_photo_collage_release_insert_value,
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
