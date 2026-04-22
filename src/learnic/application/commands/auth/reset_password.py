from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.email_tokens import (
    EmailTokenPurpose,
    EmailTokenStore,
)
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.entities.user.value_objects import RawPassword


@dataclass(slots=True, frozen=True)
class ResetPasswordCommand:
    token: str
    new_password: str


@final
class ResetPasswordCommandHandler:
    """Consume a reset-token, set a new password, log the user out everywhere."""

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        email_tokens: EmailTokenStore,
        hasher: PasswordHasher,
        refresh_store: RefreshTokenStore,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._email_tokens: Final = email_tokens
        self._hasher: Final = hasher
        self._refresh_store: Final = refresh_store

    async def run(self, data: ResetPasswordCommand) -> None:
        user_id = await self._email_tokens.consume(data.token, EmailTokenPurpose.RESET)
        user = await self._user_gateway.with_id(user_id)
        if user is None:
            raise InvalidTokenError

        user.change_password(self._hasher.hash(RawPassword(data.new_password)))
        await self._refresh_store.revoke_all_for_user(user_id)
        await self._transaction.commit()
