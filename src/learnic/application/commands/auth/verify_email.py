from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)


@dataclass(slots=True, frozen=True)
class VerifyEmailCommand:
    token: str


@final
class VerifyEmailCommandHandler:
    """Consume a verify-token and flip ``email_verified`` atomically."""

    def __init__(
        self,
        transaction: Transaction,
        email_tokens: EmailTokenStore,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._email_tokens: Final = email_tokens
        self._user_gateway: Final = user_gateway

    async def run(self, data: VerifyEmailCommand) -> None:
        user_id = await self._email_tokens.consume(data.token, EmailTokenPurpose.VERIFY)
        user = await self._user_gateway.with_id(user_id)
        if user is None:
            # User row vanished mid-flow (shouldn't happen, CASCADE aside).
            raise InvalidTokenError
        user.mark_email_verified()
        await self._transaction.commit()
