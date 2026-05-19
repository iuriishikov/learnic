from dataclasses import dataclass
from typing import Self

from learnic.entities.cohort.ids import CohortID
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.enrollment.ids import EnrollmentID
from learnic.entities.user.models import UserID


@dataclass
class WebinarDetails(BaseEntity[EnrollmentID]):
    """Webinar-specific 1:1 side data for an :class:`Enrollment`.

    Mirrors the ``Product`` / ``WebinarDetails`` split: ``oid`` is
    the parent :class:`EnrollmentID`. Only carries the cohort
    reference — webinars themselves have no progress, no release
    pin, no completion timestamp here (`completed` is signalled
    only by the parent enrollment's ``status``).

    ``student_id`` is denormalised so the
    ``UNIQUE(cohort_id, student_id)`` constraint stays
    declarative on this table.
    """

    cohort_id: CohortID
    student_id: UserID

    @classmethod
    def create(
        cls,
        *,
        enrollment_id: EnrollmentID,
        cohort_id: CohortID,
        student_id: UserID,
    ) -> Self:
        return cls(
            oid=enrollment_id,
            cohort_id=cohort_id,
            student_id=student_id,
        )
