from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import Patronymic


@dataclass(slots=True, frozen=True)
class ChangeUserPatronymicCommand:
    user_id: UserID
    value: str | None  # None clears the field


@final
class ChangeUserPatronymicCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(self, data: ChangeUserPatronymicCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        patronymic = Patronymic(data.value) if data.value is not None else None
        user.change_patronymic(patronymic)
        await self._transaction.commit()
