from collections.abc import Sequence
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.note_content import (
    NoteContentReader,
    NoteDraftView,
    DraftLessonView,
    DraftModuleView,
    LessonBlockView,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.note_block.enums import BlockType
from learnic.entities.note_block.ids import LessonBlockID
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.blocks.file_resolver import (
    collect_file_ids,
    resolve_file_views,
)
from learnic.infrastructure.persistence.blocks.registry import spec_for_row
from learnic.infrastructure.persistence.models.note_block import (
    code_blocks_table,
    file_blocks_table,
    function_graph_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    multi_choice_blocks_table,
    photo_collage_blocks_table,
    photo_collage_items_table,
    rutube_video_blocks_table,
    single_choice_blocks_table,
    text_input_blocks_table,
    video_file_blocks_table,
)
from learnic.infrastructure.persistence.models.note_lesson import (
    note_lessons_table,
)
from learnic.infrastructure.persistence.models.note_module import (
    note_modules_table,
)


async def _load_collage_items_payload(
    session: AsyncSession,
    rows: Sequence[Any],
) -> dict[LessonBlockID, list[dict[str, Any]]]:
    """Batch-load items rows for every photo-collage row in ``rows``.

    Returns ``{block_id: [item dict, ...]}`` in ``position`` order.
    Each item dict matches the canonical ``{"oid", "file_id",
    "caption"}`` payload shape consumed by the registry's photo-
    collage dispatchers (so the same code path handles draft and
    release rows).
    """
    collage_ids = [
        LessonBlockID(row.oid)
        for row in rows
        if (
            row.type
            if isinstance(row.type, BlockType)
            else BlockType(row.type)
        )
        is BlockType.PHOTO_COLLAGE
    ]
    if not collage_ids:
        return {}
    stmt = (
        sa.select(
            photo_collage_items_table.c.oid,
            photo_collage_items_table.c.block_id,
            photo_collage_items_table.c.file_id,
            photo_collage_items_table.c.caption,
        )
        .where(photo_collage_items_table.c.block_id.in_(collage_ids))
        .order_by(
            photo_collage_items_table.c.block_id.asc(),
            photo_collage_items_table.c.position.asc(),
        )
    )
    items_rows = (await session.execute(stmt)).all()
    out: dict[LessonBlockID, list[dict[str, Any]]] = {}
    for row in items_rows:
        out.setdefault(LessonBlockID(row.block_id), []).append(
            {
                "oid": str(row.oid),
                "file_id": (
                    str(row.file_id) if row.file_id is not None else None
                ),
                "caption": row.caption,
            },
        )
    return out


class _RowWithCollageItems:
    """Read-only proxy exposing ``photo_collage_items`` on a row.

    Mirrors the same shim used by the gateway adapter; lets the
    registry's existing photo-collage dispatchers consume one payload
    shape across both readers (draft + release) and the gateway.
    """

    __slots__ = ("_row", "_items")

    def __init__(
        self,
        row: Any,
        items: list[dict[str, Any]],
    ) -> None:
        self._row = row
        self._items = items

    @property
    def photo_collage_items(self) -> list[dict[str, Any]]:
        return self._items

    def __getattr__(self, name: str) -> Any:
        return getattr(self._row, name)


def _attach_collage_items(
    rows: Sequence[Any],
    items_by_block: dict[LessonBlockID, list[dict[str, Any]]],
) -> list[Any]:
    out: list[Any] = []
    for row in rows:
        block_type = (
            row.type
            if isinstance(row.type, BlockType)
            else BlockType(row.type)
        )
        if block_type is not BlockType.PHOTO_COLLAGE:
            out.append(row)
            continue
        items = items_by_block.get(LessonBlockID(row.oid), [])
        out.append(_RowWithCollageItems(row, items))
    return out


class NoteContentReaderAlchemy(NoteContentReader):
    def __init__(
        self,
        session: AsyncSession,
        file_storage: FileStorage,
    ) -> None:
        self._session: Final = session
        self._file_storage: Final = file_storage

    @override
    async def get_draft(self, product_id: ProductID) -> NoteDraftView:
        modules_stmt = (
            sa.select(
                note_modules_table.c.oid,
                note_modules_table.c.title,
                note_modules_table.c.description,
                note_modules_table.c.position,
            )
            .where(note_modules_table.c.product_id == product_id)
            .order_by(note_modules_table.c.position.asc())
        )
        modules_rows = (await self._session.execute(modules_stmt)).all()

        lessons_stmt = (
            sa.select(
                note_lessons_table.c.oid,
                note_lessons_table.c.module_id,
                note_lessons_table.c.title,
                note_lessons_table.c.position,
            )
            .where(note_lessons_table.c.product_id == product_id)
            .order_by(
                note_lessons_table.c.module_id.asc(),
                note_lessons_table.c.position.asc(),
            )
        )
        lessons_rows = (await self._session.execute(lessons_stmt)).all()

        blocks_stmt = (
            sa.select(
                lesson_blocks_table.c.oid,
                lesson_blocks_table.c.lesson_id,
                lesson_blocks_table.c.type,
                lesson_blocks_table.c.position,
                html_blocks_table.c.html,
                katex_blocks_table.c.source,
                rutube_video_blocks_table.c.external_id.label(
                    "rutube_external_id",
                ),
                rutube_video_blocks_table.c.title.label("rutube_title"),
                code_blocks_table.c.tabs.label("code_tabs"),
                single_choice_blocks_table.c.options.label(
                    "single_choice_options",
                ),
                single_choice_blocks_table.c.correct_option_id.label(
                    "single_choice_correct_option_id",
                ),
                multi_choice_blocks_table.c.options.label(
                    "multi_choice_options",
                ),
                multi_choice_blocks_table.c.correct_option_ids.label(
                    "multi_choice_correct_option_ids",
                ),
                text_input_blocks_table.c.accepted_answers.label(
                    "text_input_accepted_answers",
                ),
                text_input_blocks_table.c.case_sensitive.label(
                    "text_input_case_sensitive",
                ),
                text_input_blocks_table.c.trim_whitespace.label(
                    "text_input_trim_whitespace",
                ),
                file_blocks_table.c.file_id.label("file_block_file_id"),
                file_blocks_table.c.title.label("file_block_title"),
                video_file_blocks_table.c.file_id.label(
                    "video_file_block_file_id",
                ),
                video_file_blocks_table.c.title.label(
                    "video_file_block_title",
                ),
                photo_collage_blocks_table.c.title.label("photo_collage_title"),
                function_graph_blocks_table.c.config.label(
                    "function_graph_config",
                ),
            )
            .select_from(
                lesson_blocks_table.outerjoin(
                    html_blocks_table,
                    lesson_blocks_table.c.oid == html_blocks_table.c.oid,
                )
                .outerjoin(
                    katex_blocks_table,
                    lesson_blocks_table.c.oid == katex_blocks_table.c.oid,
                )
                .outerjoin(
                    rutube_video_blocks_table,
                    lesson_blocks_table.c.oid == rutube_video_blocks_table.c.oid,
                )
                .outerjoin(
                    code_blocks_table,
                    lesson_blocks_table.c.oid == code_blocks_table.c.oid,
                )
                .outerjoin(
                    single_choice_blocks_table,
                    lesson_blocks_table.c.oid == single_choice_blocks_table.c.oid,
                )
                .outerjoin(
                    multi_choice_blocks_table,
                    lesson_blocks_table.c.oid == multi_choice_blocks_table.c.oid,
                )
                .outerjoin(
                    text_input_blocks_table,
                    lesson_blocks_table.c.oid == text_input_blocks_table.c.oid,
                )
                .outerjoin(
                    file_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                )
                .outerjoin(
                    video_file_blocks_table,
                    lesson_blocks_table.c.oid == video_file_blocks_table.c.oid,
                )
                .outerjoin(
                    photo_collage_blocks_table,
                    lesson_blocks_table.c.oid == photo_collage_blocks_table.c.oid,
                )
                .outerjoin(
                    function_graph_blocks_table,
                    lesson_blocks_table.c.oid
                    == function_graph_blocks_table.c.oid,
                ),
            )
            .where(lesson_blocks_table.c.product_id == product_id)
            .order_by(
                lesson_blocks_table.c.lesson_id.asc(),
                lesson_blocks_table.c.position.asc(),
            )
        )
        blocks_rows = list(
            (await self._session.execute(blocks_stmt)).all(),
        )
        # Batch-load every photo-collage row's items in one query,
        # then stash them on a row proxy so the registry's photo-
        # collage dispatcher sees a payload list under the same
        # attribute name it reads on the release side.
        collage_items_payload = await _load_collage_items_payload(
            self._session,
            blocks_rows,
        )
        attached_rows = _attach_collage_items(
            blocks_rows,
            collage_items_payload,
        )
        # Pre-resolve every file referenced by the draft so the
        # registry's row_to_view dispatchers can pick up presigned
        # URLs without needing async themselves. Photo-collage items
        # contribute additional file_ids via the items payload — see
        # `collect_file_ids` for the union.
        files_by_id = await resolve_file_views(
            self._session,
            self._file_storage,
            collect_file_ids(attached_rows),
        )

        blocks_by_lesson: dict[NoteLessonID, list[LessonBlockView]] = {}
        for row in attached_rows:
            blocks_by_lesson.setdefault(
                NoteLessonID(row.lesson_id),
                [],
            ).append(spec_for_row(row).row_to_view(row, files_by_id))

        lessons_by_module: dict[NoteModuleID, list[DraftLessonView]] = {}
        for row in lessons_rows:
            lessons_by_module.setdefault(
                NoteModuleID(row.module_id),
                [],
            ).append(
                DraftLessonView(
                    oid=NoteLessonID(row.oid),
                    title=row.title,
                    position=row.position,
                    blocks=blocks_by_lesson.get(
                        NoteLessonID(row.oid),
                        [],
                    ),
                ),
            )

        modules: list[DraftModuleView] = [
            DraftModuleView(
                oid=NoteModuleID(row.oid),
                title=row.title,
                description=row.description,
                position=row.position,
                lessons=lessons_by_module.get(
                    NoteModuleID(row.oid),
                    [],
                ),
            )
            for row in modules_rows
        ]
        return NoteDraftView(product_id=product_id, modules=modules)

    @override
    async def with_block_id(
        self,
        block_id: LessonBlockID,
    ) -> tuple[ProductID, LessonBlockView] | None:
        block_stmt = (
            sa.select(
                lesson_blocks_table.c.oid,
                lesson_blocks_table.c.product_id,
                lesson_blocks_table.c.lesson_id,
                lesson_blocks_table.c.type,
                lesson_blocks_table.c.position,
                html_blocks_table.c.html,
                katex_blocks_table.c.source,
                rutube_video_blocks_table.c.external_id.label(
                    "rutube_external_id",
                ),
                rutube_video_blocks_table.c.title.label("rutube_title"),
                code_blocks_table.c.tabs.label("code_tabs"),
                single_choice_blocks_table.c.options.label(
                    "single_choice_options",
                ),
                single_choice_blocks_table.c.correct_option_id.label(
                    "single_choice_correct_option_id",
                ),
                multi_choice_blocks_table.c.options.label(
                    "multi_choice_options",
                ),
                multi_choice_blocks_table.c.correct_option_ids.label(
                    "multi_choice_correct_option_ids",
                ),
                text_input_blocks_table.c.accepted_answers.label(
                    "text_input_accepted_answers",
                ),
                text_input_blocks_table.c.case_sensitive.label(
                    "text_input_case_sensitive",
                ),
                text_input_blocks_table.c.trim_whitespace.label(
                    "text_input_trim_whitespace",
                ),
                file_blocks_table.c.file_id.label("file_block_file_id"),
                file_blocks_table.c.title.label("file_block_title"),
                video_file_blocks_table.c.file_id.label(
                    "video_file_block_file_id",
                ),
                video_file_blocks_table.c.title.label(
                    "video_file_block_title",
                ),
                photo_collage_blocks_table.c.title.label("photo_collage_title"),
                function_graph_blocks_table.c.config.label(
                    "function_graph_config",
                ),
            )
            .select_from(
                lesson_blocks_table.outerjoin(
                    html_blocks_table,
                    lesson_blocks_table.c.oid == html_blocks_table.c.oid,
                )
                .outerjoin(
                    katex_blocks_table,
                    lesson_blocks_table.c.oid == katex_blocks_table.c.oid,
                )
                .outerjoin(
                    rutube_video_blocks_table,
                    lesson_blocks_table.c.oid == rutube_video_blocks_table.c.oid,
                )
                .outerjoin(
                    code_blocks_table,
                    lesson_blocks_table.c.oid == code_blocks_table.c.oid,
                )
                .outerjoin(
                    single_choice_blocks_table,
                    lesson_blocks_table.c.oid == single_choice_blocks_table.c.oid,
                )
                .outerjoin(
                    multi_choice_blocks_table,
                    lesson_blocks_table.c.oid == multi_choice_blocks_table.c.oid,
                )
                .outerjoin(
                    text_input_blocks_table,
                    lesson_blocks_table.c.oid == text_input_blocks_table.c.oid,
                )
                .outerjoin(
                    file_blocks_table,
                    lesson_blocks_table.c.oid == file_blocks_table.c.oid,
                )
                .outerjoin(
                    video_file_blocks_table,
                    lesson_blocks_table.c.oid == video_file_blocks_table.c.oid,
                )
                .outerjoin(
                    photo_collage_blocks_table,
                    lesson_blocks_table.c.oid == photo_collage_blocks_table.c.oid,
                )
                .outerjoin(
                    function_graph_blocks_table,
                    lesson_blocks_table.c.oid
                    == function_graph_blocks_table.c.oid,
                ),
            )
            .where(lesson_blocks_table.c.oid == block_id)
        )
        row = (await self._session.execute(block_stmt)).one_or_none()
        if row is None:
            return None
        collage_items_payload = await _load_collage_items_payload(
            self._session,
            [row],
        )
        (attached,) = _attach_collage_items([row], collage_items_payload)
        files_by_id = await resolve_file_views(
            self._session,
            self._file_storage,
            collect_file_ids([attached]),
        )
        view = spec_for_row(attached).row_to_view(attached, files_by_id)
        return ProductID(row.product_id), view
