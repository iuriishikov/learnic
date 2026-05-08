from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.webinar_enrollment import (
    WebinarEnrollmentGateway,
    WebinarEnrollmentReader,
    WebinarEnrollmentView,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.ids import WebinarEnrollmentID
from learnic.entities.webinar_enrollment.models import WebinarEnrollment
from learnic.infrastructure.persistence.models.webinar_enrollment import (
    webinar_enrollments_table,
)


class WebinarEnrollmentMapperAlchemy(WebinarEnrollmentGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: WebinarEnrollmentID,
    ) -> WebinarEnrollment | None:
        stmt = sa.select(WebinarEnrollment).where(
            webinar_enrollments_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def with_cohort_and_student(
        self,
        cohort_id: CohortID,
        student_id: UserID,
    ) -> WebinarEnrollment | None:
        stmt = sa.select(WebinarEnrollment).where(
            webinar_enrollments_table.c.cohort_id == cohort_id,
            webinar_enrollments_table.c.student_id == student_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarEnrollment]:
        stmt = (
            sa.select(WebinarEnrollment)
            .where(webinar_enrollments_table.c.cohort_id == cohort_id)
            .order_by(webinar_enrollments_table.c.enrolled_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class WebinarEnrollmentReaderAlchemy(WebinarEnrollmentReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[WebinarEnrollmentView]:
        stmt = (
            sa.select(
                webinar_enrollments_table.c.oid,
                webinar_enrollments_table.c.cohort_id,
                webinar_enrollments_table.c.student_id,
                webinar_enrollments_table.c.status,
                webinar_enrollments_table.c.enrolled_at,
            )
            .where(webinar_enrollments_table.c.cohort_id == cohort_id)
            .order_by(webinar_enrollments_table.c.enrolled_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            WebinarEnrollmentView(
                oid=WebinarEnrollmentID(row.oid),
                cohort_id=CohortID(row.cohort_id),
                student_id=UserID(row.student_id),
                status=row.status,
                enrolled_at=row.enrolled_at,
            )
            for row in rows
        ]

    @override
    async def for_student(
        self,
        student_id: UserID,
    ) -> list[WebinarEnrollmentView]:
        stmt = (
            sa.select(
                webinar_enrollments_table.c.oid,
                webinar_enrollments_table.c.cohort_id,
                webinar_enrollments_table.c.student_id,
                webinar_enrollments_table.c.status,
                webinar_enrollments_table.c.enrolled_at,
            )
            .where(webinar_enrollments_table.c.student_id == student_id)
            .order_by(webinar_enrollments_table.c.enrolled_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            WebinarEnrollmentView(
                oid=WebinarEnrollmentID(row.oid),
                cohort_id=CohortID(row.cohort_id),
                student_id=UserID(row.student_id),
                status=row.status,
                enrolled_at=row.enrolled_at,
            )
            for row in rows
        ]
