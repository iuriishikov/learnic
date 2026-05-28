from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.admin_stats import (
    AdminStatsReader,
    AdminStatsView,
)


@dataclass(slots=True, frozen=True)
class GetAdminStatsQuery:
    """No-argument query — the dashboard snapshot is platform-wide."""


@final
class GetAdminStatsQueryHandler:
    """Return the admin dashboard's aggregate counters."""

    def __init__(self, reader: AdminStatsReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetAdminStatsQuery) -> AdminStatsView:  # noqa: ARG002
        return await self._reader.collect()
