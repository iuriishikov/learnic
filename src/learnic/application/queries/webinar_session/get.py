from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.webinar_session import (
    WebinarSessionReader,
    WebinarSessionView,
)
from learnic.application.common.validators import validate_empty
from learnic.entities.cohort.ids import WebinarSessionID


@dataclass(slots=True, frozen=True)
class GetWebinarSessionQuery:
    oid: WebinarSessionID


@final
class GetWebinarSessionQueryHandler:
    def __init__(self, reader: WebinarSessionReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetWebinarSessionQuery,
    ) -> WebinarSessionView:
        return validate_empty(
            await self._reader.with_id(data.oid),
            data.oid,
        )
