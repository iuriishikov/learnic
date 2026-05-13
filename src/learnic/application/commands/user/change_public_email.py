from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import PublicEmail


@dataclass(slots=True, frozen=True)
class ChangeUserPublicEmailCommand:
    user_id: UserID
    value: str | None


@final
class ChangeUserPublicEmailCommandHandler:
    """Updates the public contact email shown on the user's profile.

    Distinct from the login email — there is no verification flow on
    this field; the user is solely responsible for the address they
    publish.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway

    async def run(self, data: ChangeUserPublicEmailCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        new_value = PublicEmail(data.value) if data.value is not None else None
        user.change_public_email(new_value)
        await self._transaction.commit()
