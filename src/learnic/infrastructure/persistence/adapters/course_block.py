from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_block import (
    LessonBlockGateway,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_block.models import (
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
from learnic.entities.course_block.value_objects import AcceptedAnswer
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.infrastructure.persistence.blocks.registry import (
    _common_from_row,
    spec_for_row,
)
from learnic.infrastructure.persistence.models.course_block import (
    code_blocks_table,
    file_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    multi_choice_blocks_table,
    photo_collage_blocks_table,
    rutube_video_blocks_table,
    single_choice_blocks_table,
    text_input_blocks_table,
    video_file_blocks_table,
)


def _tabs_to_jsonb(tabs: list[CodeTab]) -> list[dict[str, str]]:
    """Serialize domain tabs into the JSONB-friendly shape stored on disk."""
    return [
        {
            "label": tab.label.value,
            "source": tab.source.value,
            "language": tab.language.value,
        }
        for tab in tabs
    ]


def _options_to_jsonb(options: list[ChoiceOption]) -> list[dict[str, str]]:
    """Serialize choice options into JSONB-friendly dicts."""
    return [{"oid": str(o.oid), "label": o.label.value} for o in options]


def _accepted_answers_to_jsonb(answers: list[AcceptedAnswer]) -> list[str]:
    """Serialize accepted answers into a JSONB string array."""
    return [a.value for a in answers]


def _collage_items_to_jsonb(
    items: list[CollageItem],
) -> list[dict[str, Any]]:
    """Serialize collage items into JSONB-friendly dicts.

    Shape mirrors what ``_jsonb_to_collage_items`` reads back: per-item
    ``file_id`` is stringified UUID (or ``None`` if the file was purged)
    and ``caption`` is the raw VO value (or ``None`` for captionless
    items).
    """
    return [
        {
            "file_id": str(item.file_id) if item.file_id is not None else None,
            "caption": (
                item.caption.value if item.caption is not None else None
            ),
        }
        for item in items
    ]


def _row_to_block(row: sa.Row[Any]) -> LessonBlock:
    """Hydrate a parent + LEFT JOIN child row into a domain entity.

    Discriminator dispatch lives in
    :data:`learnic.infrastructure.persistence.blocks.registry.BLOCK_SPECS`
    — adding a new :class:`BlockType` variant means a new spec
    instance, not another ``elif`` branch here.
    """
    spec = spec_for_row(row)
    return spec.row_to_entity(row, _common_from_row(row))


def _select_blocks() -> sa.Select[Any]:
    return sa.select(
        lesson_blocks_table.c.oid,
        lesson_blocks_table.c.lesson_id,
        lesson_blocks_table.c.product_id,
        lesson_blocks_table.c.type,
        lesson_blocks_table.c.position,
        lesson_blocks_table.c.created_at,
        lesson_blocks_table.c.updated_at,
        html_blocks_table.c.html,
        katex_blocks_table.c.source,
        rutube_video_blocks_table.c.external_id.label("rutube_external_id"),
        rutube_video_blocks_table.c.title.label("rutube_title"),
        code_blocks_table.c.tabs.label("code_tabs"),
        single_choice_blocks_table.c.options.label("single_choice_options"),
        single_choice_blocks_table.c.correct_option_id.label(
            "single_choice_correct_option_id",
        ),
        multi_choice_blocks_table.c.options.label("multi_choice_options"),
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
        video_file_blocks_table.c.file_id.label("video_file_block_file_id"),
        video_file_blocks_table.c.title.label("video_file_block_title"),
        photo_collage_blocks_table.c["items"].label("photo_collage_items"),
        photo_collage_blocks_table.c.title.label("photo_collage_title"),
    ).select_from(
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
        ),
    )


class LessonBlockGatewayAlchemy(LessonBlockGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: LessonBlockID,
    ) -> LessonBlock | None:
        stmt = _select_blocks().where(lesson_blocks_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return _row_to_block(row)

    @override
    async def list_for_lesson(
        self,
        lesson_id: CourseLessonID,
    ) -> list[LessonBlock]:
        stmt = (
            _select_blocks()
            .where(lesson_blocks_table.c.lesson_id == lesson_id)
            .order_by(lesson_blocks_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_block(row) for row in rows]

    @override
    async def add_html(self, block: HtmlBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.HTML.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(html_blocks_table).values(
                oid=block.oid,
                html=block.html.value,
            ),
        )

    @override
    async def update_html(self, block: HtmlBlock) -> None:
        await self._session.execute(
            sa.update(html_blocks_table)
            .where(html_blocks_table.c.oid == block.oid)
            .values(html=block.html.value),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_katex(self, block: KatexBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.KATEX.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(katex_blocks_table).values(
                oid=block.oid,
                source=block.source.value,
            ),
        )

    @override
    async def update_katex(self, block: KatexBlock) -> None:
        await self._session.execute(
            sa.update(katex_blocks_table)
            .where(katex_blocks_table.c.oid == block.oid)
            .values(source=block.source.value),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_rutube_video(self, block: RutubeVideoBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.RUTUBE_VIDEO.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(rutube_video_blocks_table).values(
                oid=block.oid,
                external_id=block.external_id.value,
                title=block.title.value if block.title is not None else None,
            ),
        )

    @override
    async def update_rutube_video(self, block: RutubeVideoBlock) -> None:
        await self._session.execute(
            sa.update(rutube_video_blocks_table)
            .where(rutube_video_blocks_table.c.oid == block.oid)
            .values(
                external_id=block.external_id.value,
                title=block.title.value if block.title is not None else None,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_code(self, block: CodeBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.CODE.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(code_blocks_table).values(
                oid=block.oid,
                tabs=_tabs_to_jsonb(block.tabs),
            ),
        )

    @override
    async def update_code(self, block: CodeBlock) -> None:
        await self._session.execute(
            sa.update(code_blocks_table)
            .where(code_blocks_table.c.oid == block.oid)
            .values(tabs=_tabs_to_jsonb(block.tabs)),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_single_choice(self, block: SingleChoiceBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.SINGLE_CHOICE.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(single_choice_blocks_table).values(
                oid=block.oid,
                options=_options_to_jsonb(block.options),
                correct_option_id=block.correct_option_id,
            ),
        )

    @override
    async def update_single_choice(self, block: SingleChoiceBlock) -> None:
        await self._session.execute(
            sa.update(single_choice_blocks_table)
            .where(single_choice_blocks_table.c.oid == block.oid)
            .values(
                options=_options_to_jsonb(block.options),
                correct_option_id=block.correct_option_id,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_multi_choice(self, block: MultiChoiceBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.MULTI_CHOICE.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(multi_choice_blocks_table).values(
                oid=block.oid,
                options=_options_to_jsonb(block.options),
                correct_option_ids=[str(o) for o in block.correct_option_ids],
            ),
        )

    @override
    async def update_multi_choice(self, block: MultiChoiceBlock) -> None:
        await self._session.execute(
            sa.update(multi_choice_blocks_table)
            .where(multi_choice_blocks_table.c.oid == block.oid)
            .values(
                options=_options_to_jsonb(block.options),
                correct_option_ids=[str(o) for o in block.correct_option_ids],
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_text_input(self, block: TextInputBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.TEXT_INPUT.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(text_input_blocks_table).values(
                oid=block.oid,
                accepted_answers=_accepted_answers_to_jsonb(
                    block.accepted_answers,
                ),
                case_sensitive=block.case_sensitive,
                trim_whitespace=block.trim_whitespace,
            ),
        )

    @override
    async def update_text_input(self, block: TextInputBlock) -> None:
        await self._session.execute(
            sa.update(text_input_blocks_table)
            .where(text_input_blocks_table.c.oid == block.oid)
            .values(
                accepted_answers=_accepted_answers_to_jsonb(
                    block.accepted_answers,
                ),
                case_sensitive=block.case_sensitive,
                trim_whitespace=block.trim_whitespace,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_file(self, block: FileBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.FILE.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(file_blocks_table).values(
                oid=block.oid,
                file_id=block.file_id,
                title=block.title.value if block.title is not None else None,
            ),
        )

    @override
    async def update_file(self, block: FileBlock) -> None:
        await self._session.execute(
            sa.update(file_blocks_table)
            .where(file_blocks_table.c.oid == block.oid)
            .values(
                file_id=block.file_id,
                title=block.title.value if block.title is not None else None,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_video_file(self, block: VideoFileBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.VIDEO_FILE.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(video_file_blocks_table).values(
                oid=block.oid,
                file_id=block.file_id,
                title=block.title.value if block.title is not None else None,
            ),
        )

    @override
    async def update_video_file(self, block: VideoFileBlock) -> None:
        await self._session.execute(
            sa.update(video_file_blocks_table)
            .where(video_file_blocks_table.c.oid == block.oid)
            .values(
                file_id=block.file_id,
                title=block.title.value if block.title is not None else None,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def add_photo_collage(self, block: PhotoCollageBlock) -> None:
        await self._session.execute(
            sa.insert(lesson_blocks_table).values(
                oid=block.oid,
                lesson_id=block.lesson_id,
                product_id=block.product_id,
                type=BlockType.PHOTO_COLLAGE.value,
                position=block.position,
                created_at=block.created_at,
                updated_at=block.updated_at,
            ),
        )
        await self._session.execute(
            sa.insert(photo_collage_blocks_table).values(
                oid=block.oid,
                items=_collage_items_to_jsonb(block.items),
                title=block.title.value if block.title is not None else None,
            ),
        )

    @override
    async def update_photo_collage(self, block: PhotoCollageBlock) -> None:
        await self._session.execute(
            sa.update(photo_collage_blocks_table)
            .where(photo_collage_blocks_table.c.oid == block.oid)
            .values(
                items=_collage_items_to_jsonb(block.items),
                title=block.title.value if block.title is not None else None,
            ),
        )
        await self._session.execute(
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.oid == block.oid)
            .values(updated_at=sa.func.now()),
        )

    @override
    async def delete(self, oid: LessonBlockID) -> None:
        # Child rows cascade via FK ON DELETE CASCADE.
        await self._session.execute(
            sa.delete(lesson_blocks_table).where(
                lesson_blocks_table.c.oid == oid,
            ),
        )

    @override
    async def reorder(
        self,
        lesson_id: CourseLessonID,
        ordered_ids: list[LessonBlockID],
    ) -> None:
        if not ordered_ids:
            return
        whens: dict[Any, int] = {oid: idx for idx, oid in enumerate(ordered_ids)}
        case_expr = sa.case(whens, value=lesson_blocks_table.c.oid)
        stmt = (
            sa.update(lesson_blocks_table)
            .where(lesson_blocks_table.c.lesson_id == lesson_id)
            .where(lesson_blocks_table.c.oid.in_(ordered_ids))
            .values(position=case_expr)
        )
        await self._session.execute(stmt)
