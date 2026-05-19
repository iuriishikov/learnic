from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.enrollment import (
    CourseDetailsView,
    EnrollmentGateway,
    EnrollmentReader,
    EnrollmentView,
    WebinarDetailsView,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.course_details import CourseDetails
from learnic.entities.enrollment.enums import EnrollmentType
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.enrollment.webinar_details import WebinarDetails
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.enrollment import (
    enrollment_course_details_table,
    enrollment_webinar_details_table,
    enrollments_table,
)


class EnrollmentMapperAlchemy(EnrollmentGateway):
    """Write-side gateway. Loads side details out-of-band by type.

    Same shape as :class:`ProductMapperAlchemy`: the main row is
    fetched, then a single follow-up query loads the relevant
    side-detail entity based on ``type``. Keeps the imperative
    mapping simple (no ORM relationship) and the gateway honest
    about its read pattern.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    async def _hydrate_details(self, enrollment: Enrollment) -> None:
        if enrollment.type is EnrollmentType.COURSE:
            course_stmt = sa.select(CourseDetails).where(
                enrollment_course_details_table.c.enrollment_id
                == enrollment.oid,
            )
            course_result = await self._session.execute(course_stmt)
            enrollment.course_details = course_result.scalar_one_or_none()
        else:
            webinar_stmt = sa.select(WebinarDetails).where(
                enrollment_webinar_details_table.c.enrollment_id
                == enrollment.oid,
            )
            webinar_result = await self._session.execute(webinar_stmt)
            enrollment.webinar_details = (
                webinar_result.scalar_one_or_none()
            )

    @override
    async def with_id(self, oid: EnrollmentID) -> Enrollment | None:
        stmt = sa.select(Enrollment).where(enrollments_table.c.oid == oid)
        result = await self._session.execute(stmt)
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            return None
        await self._hydrate_details(enrollment)
        return enrollment

    @override
    async def with_product_and_student(
        self,
        product_id: ProductID,
        student_id: UserID,
    ) -> Enrollment | None:
        stmt = (
            sa.select(Enrollment)
            .join(
                enrollment_course_details_table,
                enrollment_course_details_table.c.enrollment_id
                == enrollments_table.c.oid,
            )
            .where(
                enrollment_course_details_table.c.product_id == product_id,
                enrollment_course_details_table.c.student_id == student_id,
            )
        )
        result = await self._session.execute(stmt)
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            return None
        await self._hydrate_details(enrollment)
        return enrollment

    @override
    async def with_cohort_and_student(
        self,
        cohort_id: CohortID,
        student_id: UserID,
    ) -> Enrollment | None:
        stmt = (
            sa.select(Enrollment)
            .join(
                enrollment_webinar_details_table,
                enrollment_webinar_details_table.c.enrollment_id
                == enrollments_table.c.oid,
            )
            .where(
                enrollment_webinar_details_table.c.cohort_id == cohort_id,
                enrollment_webinar_details_table.c.student_id == student_id,
            )
        )
        result = await self._session.execute(stmt)
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            return None
        await self._hydrate_details(enrollment)
        return enrollment

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[Enrollment]:
        stmt = (
            sa.select(Enrollment)
            .join(
                enrollment_webinar_details_table,
                enrollment_webinar_details_table.c.enrollment_id
                == enrollments_table.c.oid,
            )
            .where(enrollment_webinar_details_table.c.cohort_id == cohort_id)
            .order_by(enrollments_table.c.enrolled_at.asc())
        )
        result = await self._session.execute(stmt)
        enrollments = list(result.scalars().all())
        for e in enrollments:
            await self._hydrate_details(e)
        return enrollments


def _select_view() -> sa.Select[Any]:
    cd = enrollment_course_details_table
    wd = enrollment_webinar_details_table
    return sa.select(
        enrollments_table.c.oid,
        enrollments_table.c.type,
        enrollments_table.c.student_id,
        enrollments_table.c.status,
        enrollments_table.c.enrolled_at,
        cd.c.product_id.label("course_product_id"),
        cd.c.release_id.label("course_release_id"),
        cd.c.progress_percent.label("course_progress_percent"),
        cd.c.completed_at.label("course_completed_at"),
        wd.c.cohort_id.label("webinar_cohort_id"),
    ).select_from(
        enrollments_table.outerjoin(
            cd,
            cd.c.enrollment_id == enrollments_table.c.oid,
        ).outerjoin(
            wd,
            wd.c.enrollment_id == enrollments_table.c.oid,
        ),
    )


def _row_to_view(row: sa.Row[Any]) -> EnrollmentView:
    course_details: CourseDetailsView | None = None
    if row.course_product_id is not None:
        course_details = CourseDetailsView(
            product_id=ProductID(row.course_product_id),
            release_id=(
                CourseReleaseID(row.course_release_id)
                if row.course_release_id is not None
                else None
            ),
            progress_percent=row.course_progress_percent,
            completed_at=row.course_completed_at,
        )
    webinar_details: WebinarDetailsView | None = None
    if row.webinar_cohort_id is not None:
        webinar_details = WebinarDetailsView(
            cohort_id=CohortID(row.webinar_cohort_id),
        )
    return EnrollmentView(
        oid=EnrollmentID(row.oid),
        type=row.type,
        student_id=UserID(row.student_id),
        status=row.status,
        enrolled_at=row.enrolled_at,
        course_details=course_details,
        webinar_details=webinar_details,
    )


class EnrollmentReaderAlchemy(EnrollmentReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[EnrollmentView]:
        cd = enrollment_course_details_table
        stmt = (
            _select_view()
            .where(cd.c.product_id == product_id)
            .order_by(enrollments_table.c.enrolled_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

    @override
    async def for_cohort(
        self,
        cohort_id: CohortID,
    ) -> list[EnrollmentView]:
        wd = enrollment_webinar_details_table
        stmt = (
            _select_view()
            .where(wd.c.cohort_id == cohort_id)
            .order_by(enrollments_table.c.enrolled_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

    @override
    async def for_student(
        self,
        student_id: UserID,
    ) -> list[EnrollmentView]:
        stmt = (
            _select_view()
            .where(enrollments_table.c.student_id == student_id)
            .order_by(enrollments_table.c.enrolled_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]
