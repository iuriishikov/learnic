from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_content import (
    CourseContentReader,
    CourseDraftView,
    DraftLessonView,
    DraftModuleView,
    LessonBlockView,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.blocks.registry import spec_for_row
from learnic.infrastructure.persistence.models.course_block import (
    code_blocks_table,
    html_blocks_table,
    katex_blocks_table,
    lesson_blocks_table,
    multi_choice_blocks_table,
    rutube_video_blocks_table,
    single_choice_blocks_table,
    text_input_blocks_table,
)
from learnic.infrastructure.persistence.models.course_lesson import (
    course_lessons_table,
)
from learnic.infrastructure.persistence.models.course_module import (
    course_modules_table,
)


def _row_to_block_view(row: sa.Row[Any]) -> LessonBlockView:
    """Hydrate a block row into its read-side view via the registry."""
    return spec_for_row(row).row_to_view(row)


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
