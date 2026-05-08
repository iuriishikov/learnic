from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.webinar_schedule import (
    WebinarScheduleReader,
    WebinarScheduleView,
)
from learnic.entities.cohort.ids import CohortID


@dataclass(slots=True, frozen=True)
class GetCohortSchedulesQuery:
    cohort_id: CohortID


@final
class GetCohortSchedulesQueryHandler:
    def __init__(self, reader: WebinarScheduleReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetCohortSchedulesQuery,
    ) -> list[WebinarScheduleView]:
        return await self._reader.for_cohort(data.cohort_id)
