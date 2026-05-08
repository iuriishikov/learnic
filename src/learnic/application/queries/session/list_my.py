from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.session import (
    SessionsReader,
    SessionView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListMySessionsQuery:
    user_id: UserID


@final
class ListMySessionsQueryHandler:
    """Returns every active refresh-token session for the user."""

    def __init__(self, reader: SessionsReader) -> None:
        self._reader: Final = reader

    async def run(self, data: ListMySessionsQuery) -> list[SessionView]:
        return await self._reader.list_for_user(data.user_id)
