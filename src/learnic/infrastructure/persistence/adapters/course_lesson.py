from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_lesson import (
    CourseLessonGateway,
)
from learnic.entities.course_lesson.ids import CourseLessonID
from learnic.entities.course_lesson.models import CourseLesson
from learnic.entities.course_module.ids import CourseModuleID
from learnic.infrastructure.persistence.models.course_lesson import (
    course_lessons_table,
)


class CourseLessonMapperAlchemy(CourseLessonGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: CourseLessonID,
    ) -> CourseLesson | None:
        stmt = sa.select(CourseLesson).where(
            course_lessons_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_module(
        self,
        module_id: CourseModuleID,
    ) -> list[CourseLesson]:
        stmt = (
            sa.select(CourseLesson)
            .where(course_lessons_table.c.module_id == module_id)
            .order_by(course_lessons_table.c.position.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete(self, lesson: CourseLesson) -> None:
        await self._session.delete(lesson)

    @override
    async def reorder(
        self,
        module_id: CourseModuleID,
        ordered_ids: list[CourseLessonID],
    ) -> None:
        if not ordered_ids:
            return
        whens: dict[Any, int] = {oid: idx for idx, oid in enumerate(ordered_ids)}
        case_expr = sa.case(whens, value=course_lessons_table.c.oid)
        stmt = (
            sa.update(course_lessons_table)
            .where(course_lessons_table.c.module_id == module_id)
            .where(course_lessons_table.c.oid.in_(ordered_ids))
            .values(position=case_expr)
        )
        await self._session.execute(stmt)
