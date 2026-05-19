from dataclasses import dataclass
from datetime import datetime
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.enrollment.value_objects import ProgressPercent
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass
class CourseDetails(BaseEntity[EnrollmentID]):
    """Course-specific 1:1 side data for an :class:`Enrollment`.

    Mirrors the ``Product`` / ``WebinarDetails`` split: ``oid`` is
    the parent :class:`EnrollmentID`, the row carries everything
    that exists only for ``EnrollmentType.COURSE``.

    ``student_id`` is denormalised from the parent ``Enrollment``
    so the ``UNIQUE(product_id, student_id)`` constraint can live
    directly on this table — Postgres unique constraints span one
    table only. The two values are kept in sync at creation; the
    domain never mutates either.
    """

    product_id: ProductID
    student_id: UserID
    release_id: CourseReleaseID
    progress: ProgressPercent
    completed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        enrollment_id: EnrollmentID,
        product_id: ProductID,
        student_id: UserID,
        release_id: CourseReleaseID,
        progress: ProgressPercent,
    ) -> Self:
        return cls(
            oid=enrollment_id,
            product_id=product_id,
            student_id=student_id,
            release_id=release_id,
            progress=progress,
            completed_at=None,
        )
