from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.ping import PingReader


@dataclass(slots=True, frozen=True)
class PingQuery:
    pass


@dataclass(slots=True, frozen=True)
class PingOutput:
    database: str


@final
class PingQueryHandler:
    def __init__(self, reader: PingReader) -> None:
        self._reader: Final = reader

    async def run(self, data: PingQuery) -> PingOutput:
        await self._reader.ping()
        return PingOutput(database="ok")
