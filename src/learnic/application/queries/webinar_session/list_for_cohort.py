from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.webinar_session import (
    WebinarSessionReader,
    WebinarSessionView,
)
from learnic.entities.cohort.ids import CohortID


@dataclass(slots=True, frozen=True)
class GetCohortSessionsQuery:
    cohort_id: CohortID


@final
class GetCohortSessionsQueryHandler:
    def __init__(self, reader: WebinarSessionReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetCohortSessionsQuery,
    ) -> list[WebinarSessionView]:
        return await self._reader.for_cohort(data.cohort_id)
