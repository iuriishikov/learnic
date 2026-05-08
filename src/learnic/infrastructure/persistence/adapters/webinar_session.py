from datetime import datetime
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.webinar_session import (
    WebinarSessionGateway,
    WebinarSessionReader,
    WebinarSessionView,
)
from learnic.entities.cohort.ids import (
    CohortID,
    WebinarScheduleID,
    WebinarSessionID,
)
from learnic.entities.cohort.session import WebinarSession
from learnic.infrastructure.persistence.models.cohort import (
    webinar_sessions_table,
)


def _row_to_view(row: sa.Row[Any]) -> WebinarSessionView:
    return WebinarSessionView(
        oid=WebinarSessionID(row.oid),
        cohort_id=CohortID(row.cohort_id),
        schedule_id=(
            WebinarScheduleID(row.schedule_id) if row.schedule_id is not None else None
        ),
        original_starts_at=row.original_starts_at,
        starts_at=row.starts_at,
        duration_minutes=row.duration_minutes,
        status=row.status,
        cancellation_reason=row.cancellation_reason,
        stream_url=row.stream_url,
        recording_url=row.recording_url,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class WebinarSessionMapperAlchemy(WebinarSessionGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: WebinarSessionID,
    ) -> WebinarSession | None:
        stmt = sa.select(WebinarSession).where(
            webinar_sessions_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarSession]:
        stmt = (
            sa.select(WebinarSession)
            .where(webinar_sessions_table.c.cohort_id == cohort_id)
            .order_by(webinar_sessions_table.c.starts_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def last_original_starts_at(
        self,
        schedule_id: WebinarScheduleID,
    ) -> datetime | None:
        stmt = sa.select(
            sa.func.max(webinar_sessions_table.c.original_starts_at),
        ).where(webinar_sessions_table.c.schedule_id == schedule_id)
        result = await self._session.execute(stmt)
        value: datetime | None = result.scalar_one_or_none()
        return value

    @override
    async def delete(self, session: WebinarSession) -> None:
        await self._session.delete(session)


class WebinarSessionReaderAlchemy(WebinarSessionReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: WebinarSessionID,
    ) -> WebinarSessionView | None:
        stmt = sa.select(
            webinar_sessions_table.c.oid,
            webinar_sessions_table.c.cohort_id,
            webinar_sessions_table.c.schedule_id,
            webinar_sessions_table.c.original_starts_at,
            webinar_sessions_table.c.starts_at,
            webinar_sessions_table.c.duration_minutes,
            webinar_sessions_table.c.status,
            webinar_sessions_table.c.cancellation_reason,
            webinar_sessions_table.c.stream_url,
            webinar_sessions_table.c.recording_url,
            webinar_sessions_table.c.created_at,
            webinar_sessions_table.c.updated_at,
        ).where(webinar_sessions_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return _row_to_view(row)

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarSessionView]:
        stmt = (
            sa.select(
                webinar_sessions_table.c.oid,
                webinar_sessions_table.c.cohort_id,
                webinar_sessions_table.c.schedule_id,
                webinar_sessions_table.c.original_starts_at,
                webinar_sessions_table.c.starts_at,
                webinar_sessions_table.c.duration_minutes,
                webinar_sessions_table.c.status,
                webinar_sessions_table.c.cancellation_reason,
                webinar_sessions_table.c.stream_url,
                webinar_sessions_table.c.recording_url,
                webinar_sessions_table.c.created_at,
                webinar_sessions_table.c.updated_at,
            )
            .where(webinar_sessions_table.c.cohort_id == cohort_id)
            .order_by(webinar_sessions_table.c.starts_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]
