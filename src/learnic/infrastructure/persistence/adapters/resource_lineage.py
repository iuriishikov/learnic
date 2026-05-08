from typing import Final
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.auth.resource_lineage import (
    LessonLineage,
    ModuleLineage,
    ResourceLineageReader,
)
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.course_lesson import (
    course_lessons_table,
)
from learnic.infrastructure.persistence.models.course_module import (
    course_modules_table,
)


class ResourceLineageReaderAlchemy(ResourceLineageReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def lineage_for_lesson(
        self,
        lesson_id: UUID,
    ) -> LessonLineage | None:
        stmt = sa.select(
            course_lessons_table.c.oid,
            course_lessons_table.c.module_id,
            course_lessons_table.c.product_id,
        ).where(course_lessons_table.c.oid == lesson_id)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return LessonLineage(
            lesson_id=row.oid,
            module_id=row.module_id,
            product_id=ProductID(row.product_id),
        )

    @override
    async def lineage_for_module(
        self,
        module_id: UUID,
    ) -> ModuleLineage | None:
        stmt = sa.select(
            course_modules_table.c.oid,
            course_modules_table.c.product_id,
        ).where(course_modules_table.c.oid == module_id)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return ModuleLineage(
            module_id=row.oid,
            product_id=ProductID(row.product_id),
        )
