from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.cohort import (
    CohortReader,
    CohortView,
)
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class GetWebinarCohortsQuery:
    webinar_id: ProductID


@final
class GetWebinarCohortsQueryHandler:
    """Returns cohorts attached to a webinar product, by ascending start date."""

    def __init__(self, reader: CohortReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetWebinarCohortsQuery,
    ) -> list[CohortView]:
        return await self._reader.for_webinar(data.webinar_id)
