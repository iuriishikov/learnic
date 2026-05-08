from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.cohort.models import Cohort
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CohortView:
    """Read-side projection of :class:`Cohort`."""

    oid: CohortID
    webinar_id: ProductID
    host_id: UserID
    name: str | None
    max_participants: int | None
    starts_on: date
    ends_on: date | None
    enrollment_status: CohortEnrollmentStatus
    lifecycle_status: CohortLifecycleStatus
    created_at: datetime


class CohortGateway(Protocol):
    """Write-side lookups for :class:`Cohort`."""

    async def with_id(self, oid: CohortID) -> Cohort | None: ...

    async def for_webinar(
        self,
        webinar_id: ProductID,
    ) -> list[Cohort]: ...


class CohortReader(Protocol):
    """Read-side queries returning :class:`CohortView` projections."""

    async def with_id(self, oid: CohortID) -> CohortView | None: ...

    async def for_webinar(
        self,
        webinar_id: ProductID,
    ) -> list[CohortView]: ...
