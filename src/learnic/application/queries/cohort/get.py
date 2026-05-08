from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.cohort import (
    CohortReader,
    CohortView,
)
from learnic.application.common.validators import validate_empty
from learnic.entities.cohort.ids import CohortID


@dataclass(slots=True, frozen=True)
class GetCohortQuery:
    oid: CohortID


@final
class GetCohortQueryHandler:
    def __init__(self, reader: CohortReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetCohortQuery) -> CohortView:
        return validate_empty(
            await self._reader.with_id(data.oid),
            data.oid,
        )
