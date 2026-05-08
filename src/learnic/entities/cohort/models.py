import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Self

from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.cohort.value_objects import CohortName
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import ParticipantsLimit
from learnic.entities.user.models import UserID


@dataclass
class Cohort(BaseEntity[CohortID]):
    """A single stream/cohort of a webinar product.

    Belongs to a webinar (``webinar_id`` references the
    ``WebinarDetails.product_id`` 1:1 row, not ``products.oid``
    directly — semantic contract: this cohort's parent product
    has webinar details). Its host (``host_id``) is the User
    running the sessions; whether they are *allowed* to host is
    enforced in business logic, not at FK level.

    Schedules attached to the cohort live as separate child
    entities (:class:`WebinarSchedule`) — loaded out-of-band via
    ``WebinarScheduleGateway``, like ProductQA in Product.
    """

    webinar_id: ProductID
    host_id: UserID
    starts_on: date
    enrollment_status: CohortEnrollmentStatus
    lifecycle_status: CohortLifecycleStatus
    created_at: datetime
    name: CohortName | None = None
    max_participants: ParticipantsLimit | None = None
    ends_on: date | None = None

    def rename(self, new_name: CohortName | None) -> None:
        self.name = new_name

    def change_max_participants(
        self,
        new_max: ParticipantsLimit | None,
    ) -> None:
        self.max_participants = new_max

    def reschedule(
        self,
        new_starts_on: date,
        new_ends_on: date | None,
    ) -> None:
        self.starts_on = new_starts_on
        self.ends_on = new_ends_on

    def open_enrollment(self) -> None:
        self.enrollment_status = CohortEnrollmentStatus.OPEN

    def close_enrollment(self) -> None:
        self.enrollment_status = CohortEnrollmentStatus.CLOSED

    def mark_full(self) -> None:
        self.enrollment_status = CohortEnrollmentStatus.FULL

    def start(self) -> None:
        self.lifecycle_status = CohortLifecycleStatus.ACTIVE

    def complete(self) -> None:
        self.lifecycle_status = CohortLifecycleStatus.COMPLETED

    def cancel(self) -> None:
        self.lifecycle_status = CohortLifecycleStatus.CANCELLED

    @classmethod
    def create(
        cls,
        webinar_id: ProductID,
        host_id: UserID,
        starts_on: date,
        name: CohortName | None = None,
        max_participants: ParticipantsLimit | None = None,
        ends_on: date | None = None,
    ) -> Self:
        return cls(
            oid=CohortID(uuid.uuid4()),
            webinar_id=webinar_id,
            host_id=host_id,
            starts_on=starts_on,
            enrollment_status=CohortEnrollmentStatus.OPEN,
            lifecycle_status=CohortLifecycleStatus.UPCOMING,
            created_at=datetime.now(timezone.utc),
            name=name,
            max_participants=max_participants,
            ends_on=ends_on,
        )
