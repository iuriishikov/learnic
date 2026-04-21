from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.user import UserReader, UserView
from learnic.application.common.validators import validate_empty
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserQuery:
    oid: UserID


@final
class GetUserQueryHandler:
    def __init__(self, reader: UserReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetUserQuery) -> UserView:
        view = await self._reader.with_id(data.oid)
        return validate_empty(view, data.oid)
