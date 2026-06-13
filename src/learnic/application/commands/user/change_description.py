from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.html import HtmlSanitizer
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import UserDescription


@dataclass(slots=True, frozen=True)
class ChangeUserDescriptionCommand:
    user_id: UserID
    html: str | None  # None clears the description


@final
class ChangeUserDescriptionCommandHandler:
    """Sanitizes user-supplied HTML, then stores the description."""

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        html_sanitizer: HtmlSanitizer,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._html_sanitizer: Final = html_sanitizer

    async def run(self, data: ChangeUserDescriptionCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        if data.html is None:
            user.change_description(None)
        else:
            sanitized = await self._html_sanitizer.sanitize(data.html)
            user.change_description(UserDescription(sanitized))
        await self._transaction.commit()
