from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import WebsiteUrl


@dataclass(slots=True, frozen=True)
class ChangeUserWebsiteUrlCommand:
    user_id: UserID
    value: str | None


@final
class ChangeUserWebsiteUrlCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(self, data: ChangeUserWebsiteUrlCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        new_value = WebsiteUrl(data.value) if data.value is not None else None
        user.change_website_url(new_value)
        await self._transaction.commit()
