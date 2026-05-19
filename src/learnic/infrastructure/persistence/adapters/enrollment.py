from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.enrollment import (
    CourseEnrollmentDetailsView,
    EnrollmentGateway,
    EnrollmentReader,
    EnrollmentView,
)
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.details import (
    CourseEnrollmentDetails,
    EnrollmentDetails,
)
from learnic.entities.enrollment.enums import (
    EnrollmentKind,
    EnrollmentStatus,
)
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.enrollment import (
    enrollment_course_details_table,
    enrollments_table,
)


class EnrollmentMapperAlchemy(EnrollmentGateway):
    """Write-side gateway.

    Inserts the parent row + matching subtype row inside the
    caller's transaction (commit stays with the application
    handler). Loads rebuild the polymorphic ``details`` body by
    dispatching on ``kind`` — same pattern as
    :class:`NotificationGatewayAlchemy`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    async def _hydrate_details(self, enrollment: Enrollment) -> None:
        if enrollment.kind is EnrollmentKind.COURSE:
            enrollment.details = await self._load_course_details(
                enrollment.oid,
            )
            return
        # No other kinds yet — defensive fallback keeps the base
        # empty body so callers can still operate on the parent.
        enrollment.details = EnrollmentDetails()

    async def _load_course_details(
        self,
        enrollment_id: EnrollmentID,
    ) -> CourseEnrollmentDetails:
        cd = enrollment_course_details_table
        stmt = sa.select(
            cd.c.release_id,
            cd.c.progress_percent,
            cd.c.completed_at,
        ).where(cd.c.enrollment_id == enrollment_id)
        row = (await self._session.execute(stmt)).one()
        return CourseEnrollmentDetails(
            release_id=CourseReleaseID(row.release_id),
            progress=ProgressPercent(row.progress_percent),
            completed_at=row.completed_at,
        )

    @override
    async def add(self, enrollment: Enrollment) -> None:
        await self._session.execute(
            sa.insert(enrollments_table).values(
                oid=enrollment.oid,
                kind=enrollment.kind.value,
                product_id=enrollment.product_id,
                student_id=enrollment.student_id,
                status=enrollment.status.value,
                enrolled_at=enrollment.enrolled_at,
            ),
        )
        if enrollment.kind is EnrollmentKind.COURSE:
            assert isinstance(  # noqa: S101
                enrollment.details,
                CourseEnrollmentDetails,
            )
            await self._session.execute(
                sa.insert(enrollment_course_details_table).values(
                    enrollment_id=enrollment.oid,
                    release_id=enrollment.details.release_id,
                    progress_percent=enrollment.details.progress.value,
                    completed_at=enrollment.details.completed_at,
                ),
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
        stmt = sa.select(Enrollment).where(
            enrollments_table.c.product_id == product_id,
            enrollments_table.c.student_id == student_id,
        )
        result = await self._session.execute(stmt)
        enrollment = result.scalar_one_or_none()
        if enrollment is None:
            return None
        await self._hydrate_details(enrollment)
        return enrollment

    @override
    async def is_enrolled(
        self,
        student_id: UserID,
        product_id: ProductID,
    ) -> bool:
        stmt = sa.select(sa.literal(True)).where(
            enrollments_table.c.product_id == product_id,
            enrollments_table.c.student_id == student_id,
            enrollments_table.c.status == EnrollmentStatus.ACTIVE.value,
        )
        result = await self._session.execute(stmt)
        return result.scalar() is not None


def _select_view() -> sa.Select[Any]:
    cd = enrollment_course_details_table
    return sa.select(
        enrollments_table.c.oid,
        enrollments_table.c.kind,
        enrollments_table.c.product_id,
        enrollments_table.c.student_id,
        enrollments_table.c.status,
        enrollments_table.c.enrolled_at,
        cd.c.release_id.label("course_release_id"),
        cd.c.progress_percent.label("course_progress_percent"),
        cd.c.completed_at.label("course_completed_at"),
    ).select_from(
        enrollments_table.outerjoin(
            cd,
            cd.c.enrollment_id == enrollments_table.c.oid,
        ),
    )


def _row_to_view(row: sa.Row[Any]) -> EnrollmentView:
    kind = EnrollmentKind(row.kind)
    details: CourseEnrollmentDetailsView | None = None
    if kind is EnrollmentKind.COURSE:
        details = CourseEnrollmentDetailsView(
            release_id=(
                CourseReleaseID(row.course_release_id)
                if row.course_release_id is not None
                else None
            ),
            progress_percent=row.course_progress_percent,
            completed_at=row.course_completed_at,
        )
    return EnrollmentView(
        oid=EnrollmentID(row.oid),
        kind=kind,
        product_id=ProductID(row.product_id),
        student_id=UserID(row.student_id),
        status=row.status,
        enrolled_at=row.enrolled_at,
        details=details,
    )


class EnrollmentReaderAlchemy(EnrollmentReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[EnrollmentView]:
        stmt = (
            _select_view()
            .where(enrollments_table.c.product_id == product_id)
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
