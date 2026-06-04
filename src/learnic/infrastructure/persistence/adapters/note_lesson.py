from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.note_lesson import (
    NoteLessonGateway,
)
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_lesson.models import NoteLesson
from learnic.entities.note_module.ids import NoteModuleID
from learnic.infrastructure.persistence.models.note_lesson import (
    note_lessons_table,
)


class NoteLessonMapperAlchemy(NoteLessonGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def lock_for_module(self, module_id: NoteModuleID) -> None:
        await self._session.execute(
            sa.text(
                "SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))",
            ),
            {"k": str(module_id)},
        )

    @override
    async def with_id(
        self,
        oid: NoteLessonID,
    ) -> NoteLesson | None:
        stmt = sa.select(NoteLesson).where(
            note_lessons_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_module(
        self,
        module_id: NoteModuleID,
    ) -> list[NoteLesson]:
        stmt = (
            sa.select(NoteLesson)
            .where(note_lessons_table.c.module_id == module_id)
            .order_by(note_lessons_table.c.position.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete(self, lesson: NoteLesson) -> None:
        await self._session.delete(lesson)

    @override
    async def reorder(
        self,
        module_id: NoteModuleID,
        ordered_ids: list[NoteLessonID],
    ) -> None:
        if not ordered_ids:
            return
        whens: dict[Any, int] = {oid: idx for idx, oid in enumerate(ordered_ids)}
        case_expr = sa.case(whens, value=note_lessons_table.c.oid)
        stmt = (
            sa.update(note_lessons_table)
            .where(note_lessons_table.c.module_id == module_id)
            .where(note_lessons_table.c.oid.in_(ordered_ids))
            .values(position=case_expr)
        )
        await self._session.execute(stmt)
