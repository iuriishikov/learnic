from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.course_enrollment import (
    CourseEnrollmentGateway,
    CourseEnrollmentReader,
    CourseEnrollmentView,
)
from learnic.entities.course_enrollment.ids import CourseEnrollmentID
from learnic.entities.course_enrollment.models import CourseEnrollment
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.course_enrollment import (
    course_enrollments_table,
)


def _row_to_view(row: sa.Row[Any]) -> CourseEnrollmentView:
    return CourseEnrollmentView(
        oid=CourseEnrollmentID(row.oid),
        product_id=ProductID(row.product_id),
        student_id=UserID(row.student_id),
        release_id=(
            CourseReleaseID(row.release_id) if row.release_id is not None else None
        ),
        status=row.status,
        progress_percent=row.progress_percent,
        enrolled_at=row.enrolled_at,
        completed_at=row.completed_at,
    )


def _select_view() -> sa.Select[Any]:
    return sa.select(
        course_enrollments_table.c.oid,
        course_enrollments_table.c.product_id,
        course_enrollments_table.c.student_id,
        course_enrollments_table.c.release_id,
        course_enrollments_table.c.status,
        course_enrollments_table.c.progress_percent,
        course_enrollments_table.c.enrolled_at,
        course_enrollments_table.c.completed_at,
    )


class CourseEnrollmentMapperAlchemy(CourseEnrollmentGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(
        self,
        oid: CourseEnrollmentID,
    ) -> CourseEnrollment | None:
        stmt = sa.select(CourseEnrollment).where(
            course_enrollments_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def with_product_and_student(
        self,
        product_id: ProductID,
        student_id: UserID,
    ) -> CourseEnrollment | None:
        stmt = sa.select(CourseEnrollment).where(
            course_enrollments_table.c.product_id == product_id,
            course_enrollments_table.c.student_id == student_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseEnrollment]:
        stmt = (
            sa.select(CourseEnrollment)
            .where(course_enrollments_table.c.product_id == product_id)
            .order_by(course_enrollments_table.c.enrolled_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class CourseEnrollmentReaderAlchemy(CourseEnrollmentReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseEnrollmentView]:
        stmt = (
            _select_view()
            .where(course_enrollments_table.c.product_id == product_id)
            .order_by(course_enrollments_table.c.enrolled_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]

    @override
    async def for_student(
        self,
        student_id: UserID,
    ) -> list[CourseEnrollmentView]:
        stmt = (
            _select_view()
            .where(course_enrollments_table.c.student_id == student_id)
            .order_by(course_enrollments_table.c.enrolled_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [_row_to_view(row) for row in rows]
