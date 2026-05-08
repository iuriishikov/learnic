from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleGateway,
    WebinarScheduleReader,
    WebinarScheduleView,
)
from learnic.entities.cohort.ids import CohortID, WebinarScheduleID
from learnic.entities.cohort.schedule import WebinarSchedule
from learnic.infrastructure.persistence.models.cohort import (
    webinar_schedules_table,
)


class WebinarScheduleMapperAlchemy(WebinarScheduleGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: WebinarScheduleID,
    ) -> WebinarSchedule | None:
        stmt = sa.select(WebinarSchedule).where(
            webinar_schedules_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarSchedule]:
        stmt = (
            sa.select(WebinarSchedule)
            .where(webinar_schedules_table.c.cohort_id == cohort_id)
            .order_by(webinar_schedules_table.c.starts_on.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete(self, schedule: WebinarSchedule) -> None:
        await self._session.delete(schedule)


class WebinarScheduleReaderAlchemy(WebinarScheduleReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarScheduleView]:
        stmt = (
            sa.select(
                webinar_schedules_table.c.oid,
                webinar_schedules_table.c.cohort_id,
                webinar_schedules_table.c.timezone,
                webinar_schedules_table.c.starts_on,
                webinar_schedules_table.c.ends_on,
                webinar_schedules_table.c.rrule,
                webinar_schedules_table.c.duration_minutes,
                webinar_schedules_table.c.created_at,
            )
            .where(webinar_schedules_table.c.cohort_id == cohort_id)
            .order_by(webinar_schedules_table.c.starts_on.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            WebinarScheduleView(
                oid=WebinarScheduleID(row.oid),
                cohort_id=CohortID(row.cohort_id),
                timezone=row.timezone,
                starts_on=row.starts_on,
                ends_on=row.ends_on,
                rrule=row.rrule,
                duration_minutes=row.duration_minutes,
                created_at=row.created_at,
            )
            for row in rows
        ]
