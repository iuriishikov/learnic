from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.cohort import (
    CohortGateway,
    CohortReader,
    CohortView,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.cohort.models import Cohort
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.cohort import cohorts_table


class CohortMapperAlchemy(CohortGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: CohortID) -> Cohort | None:
        stmt = sa.select(Cohort).where(cohorts_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_webinar(
        self,
        webinar_id: ProductID,
    ) -> list[Cohort]:
        stmt = (
            sa.select(Cohort)
            .where(cohorts_table.c.webinar_id == webinar_id)
            .order_by(cohorts_table.c.starts_on.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CohortReaderAlchemy(CohortReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: CohortID) -> CohortView | None:
        stmt = sa.select(
            cohorts_table.c.oid,
            cohorts_table.c.webinar_id,
            cohorts_table.c.host_id,
            cohorts_table.c.name,
            cohorts_table.c.max_participants,
            cohorts_table.c.starts_on,
            cohorts_table.c.ends_on,
            cohorts_table.c.enrollment_status,
            cohorts_table.c.lifecycle_status,
            cohorts_table.c.created_at,
        ).where(cohorts_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return CohortView(
            oid=CohortID(row.oid),
            webinar_id=ProductID(row.webinar_id),
            host_id=UserID(row.host_id),
            name=row.name,
            max_participants=row.max_participants,
            starts_on=row.starts_on,
            ends_on=row.ends_on,
            enrollment_status=row.enrollment_status,
            lifecycle_status=row.lifecycle_status,
            created_at=row.created_at,
        )

    @override
    async def for_webinar(
        self,
        webinar_id: ProductID,
    ) -> list[CohortView]:
        stmt = (
            sa.select(
                cohorts_table.c.oid,
                cohorts_table.c.webinar_id,
                cohorts_table.c.host_id,
                cohorts_table.c.name,
                cohorts_table.c.max_participants,
                cohorts_table.c.starts_on,
                cohorts_table.c.ends_on,
                cohorts_table.c.enrollment_status,
                cohorts_table.c.lifecycle_status,
                cohorts_table.c.created_at,
            )
            .where(cohorts_table.c.webinar_id == webinar_id)
            .order_by(cohorts_table.c.starts_on.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            CohortView(
                oid=CohortID(row.oid),
                webinar_id=ProductID(row.webinar_id),
                host_id=UserID(row.host_id),
                name=row.name,
                max_participants=row.max_participants,
                starts_on=row.starts_on,
                ends_on=row.ends_on,
                enrollment_status=row.enrollment_status,
                lifecycle_status=row.lifecycle_status,
                created_at=row.created_at,
            )
            for row in rows
        ]
