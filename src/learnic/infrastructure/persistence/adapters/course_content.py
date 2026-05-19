from typing import Final

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
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.blocks.file_resolver import (
    collect_file_ids,
    resolve_file_views,
)
from learnic.infrastructure.persistence.blocks.registry import spec_for_row
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
from learnic.infrastructure.persistence.models.course_lesson import (
    course_lessons_table,
)
from learnic.infrastructure.persistence.models.course_module import (
    course_modules_table,
)


class CourseContentReaderAlchemy(CourseContentReader):
    def __init__(
        self,
        session: AsyncSession,
        file_storage: FileStorage,
    ) -> None:
        self._session: Final = session
        self._file_storage: Final = file_storage

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
                file_blocks_table.c.file_id.label("file_block_file_id"),
                file_blocks_table.c.title.label("file_block_title"),
                video_file_blocks_table.c.file_id.label(
                    "video_file_block_file_id",
                ),
                video_file_blocks_table.c.title.label(
                    "video_file_block_title",
                ),
                photo_collage_blocks_table.c["items"].label("photo_collage_items"),
                photo_collage_blocks_table.c.title.label("photo_collage_title"),
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
        # Pre-resolve every file referenced by the draft so the
        # registry's row_to_view dispatchers can pick up presigned
        # URLs without needing async themselves. Photo-collage items
        # contribute additional file_ids via the JSONB column — see
        # `collect_file_ids` for the union.
        files_by_id = await resolve_file_views(
            self._session,
            self._file_storage,
            collect_file_ids(blocks_rows),
        )

        blocks_by_lesson: dict[CourseLessonID, list[LessonBlockView]] = {}
        for row in blocks_rows:
            blocks_by_lesson.setdefault(
                CourseLessonID(row.lesson_id),
                [],
            ).append(spec_for_row(row).row_to_view(row, files_by_id))

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
