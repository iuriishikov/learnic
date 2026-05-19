from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.cohort._authorization import (
    assert_cohort_authorized,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.cohort import CohortGateway
from learnic.application.common.persistence.enrollment import (
    EnrollmentReader,
    EnrollmentView,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetCohortEnrollmentsQuery:
    actor_id: UserID
    cohort_id: CohortID


@final
class GetCohortEnrollmentsQueryHandler:
    """List webinar-type enrollments of a cohort — host/author only.

    The student-facing equivalent
    :class:`GetStudentEnrollmentsQueryHandler` returns the
    student's own rows across both types without ownership check.
    """

    def __init__(
        self,
        reader: EnrollmentReader,
        cohort_gateway: CohortGateway,
        authorizer: Authorizer,
    ) -> None:
        self._reader: Final = reader
        self._cohort_gateway: Final = cohort_gateway
        self._authorizer: Final = authorizer

    async def run(
        self,
        data: GetCohortEnrollmentsQuery,
    ) -> list[EnrollmentView]:
        cohort = await self._cohort_gateway.with_id(data.cohort_id)
        if cohort is None:
            raise EntityNotFoundError(data.cohort_id)
        await assert_cohort_authorized(
            cohort,
            data.actor_id,
            self._authorizer,
        )
        return await self._reader.for_cohort(data.cohort_id)
