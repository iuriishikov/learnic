from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_content import (
    CodeBlockView,
    CodeTabView,
    CourseContentReader,
    CourseDraftView,
    DraftLessonView,
    DraftModuleView,
    HtmlBlockView,
    KatexBlockView,
    LessonBlockView,
    RutubeVideoBlockView,
)
from learnic.entities.course_block.enums import BlockType
from learnic.entities.course_block.ids import LessonBlockID
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.course_block import (
    code_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    rutube_video_blocks_table,
)
from learnic.infrastructure.persistence.models.course_lesson import (
    course_lessons_table,
)
from learnic.infrastructure.persistence.models.course_module import (
    course_modules_table,
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


def _row_to_block_view(row: sa.Row[Any]) -> LessonBlockView:
    block_type = BlockType(row.type)
    if block_type is BlockType.HTML:
        return HtmlBlockView(
            type=BlockType.HTML,
            oid=LessonBlockID(row.oid),
            position=row.position,
            html=row.html,
        )
    if block_type is BlockType.KATEX:
        return KatexBlockView(
            type=BlockType.KATEX,
            oid=LessonBlockID(row.oid),
            position=row.position,
            source=row.source,
        )
    if block_type is BlockType.CODE:
        return CodeBlockView(
            type=BlockType.CODE,
            oid=LessonBlockID(row.oid),
            position=row.position,
            tabs=_jsonb_to_tab_views(row.code_tabs),
        )
    return RutubeVideoBlockView(
        type=BlockType.RUTUBE_VIDEO,
        oid=LessonBlockID(row.oid),
        position=row.position,
        external_id=row.rutube_external_id,
        title=row.rutube_title,
    )


class CourseContentReaderAlchemy(CourseContentReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def get_draft(self, product_id: ProductID) -> CourseDraftView:
        modules_stmt = (
            sa.select(
                course_modules_table.c.oid,
                course_modules_table.c.title,
                course_modules_table.c.description,
                course_modules_table.c.position,
            )
            .where(course_modules_table.c.product_id == product_id)
            .order_by(course_modules_table.c.position.asc())
        )
        modules_rows = (await self._session.execute(modules_stmt)).all()

        lessons_stmt = (
            sa.select(
                course_lessons_table.c.oid,
                course_lessons_table.c.module_id,
                course_lessons_table.c.title,
                course_lessons_table.c.position,
            )
            .where(course_lessons_table.c.product_id == product_id)
            .order_by(
                course_lessons_table.c.module_id.asc(),
                course_lessons_table.c.position.asc(),
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
                ),
            )
            .where(lesson_blocks_table.c.product_id == product_id)
            .order_by(
                lesson_blocks_table.c.lesson_id.asc(),
                lesson_blocks_table.c.position.asc(),
            )
        )
        blocks_rows = (await self._session.execute(blocks_stmt)).all()

        blocks_by_lesson: dict[CourseLessonID, list[LessonBlockView]] = {}
        for row in blocks_rows:
            blocks_by_lesson.setdefault(
                CourseLessonID(row.lesson_id),
                [],
            ).append(_row_to_block_view(row))

        lessons_by_module: dict[CourseModuleID, list[DraftLessonView]] = {}
        for row in lessons_rows:
            lessons_by_module.setdefault(
                CourseModuleID(row.module_id),
                [],
            ).append(
                DraftLessonView(
                    oid=CourseLessonID(row.oid),
                    title=row.title,
                    position=row.position,
                    blocks=blocks_by_lesson.get(
                        CourseLessonID(row.oid),
                        [],
                    ),
                ),
            )

        modules: list[DraftModuleView] = [
            DraftModuleView(
                oid=CourseModuleID(row.oid),
                title=row.title,
                description=row.description,
                position=row.position,
                lessons=lessons_by_module.get(
                    CourseModuleID(row.oid),
                    [],
                ),
            )
            for row in modules_rows
        ]
        return CourseDraftView(product_id=product_id, modules=modules)
