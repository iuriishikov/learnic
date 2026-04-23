from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import LastName


@dataclass(slots=True, frozen=True)
class ChangeUserLastNameCommand:
    user_id: UserID
    value: str


@final
class ChangeUserLastNameCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(self, data: ChangeUserLastNameCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        user.change_last_name(LastName(data.value))
        await self._transaction.commit()
