from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.value_objects import RawPassword
from learnic.infrastructure.configs import SecurityConfig


@dataclass(slots=True, frozen=True)
class ResetPasswordCommand:
    token: str
    new_password: str


@final
class ResetPasswordCommandHandler:
    """Consume a reset-token, set a new password, log the user out everywhere.

    Every refresh family the user had is revoked **and** added to the
    family denylist so any in-flight access JWT (still valid by
    ``exp``) is rejected on the next request.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        email_tokens: EmailTokenStore,
        hasher: PasswordHasher,
        refresh_store: RefreshTokenStore,
        denylist: TokenDenylist,
        security_config: SecurityConfig,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._email_tokens: Final = email_tokens
        self._hasher: Final = hasher
        self._refresh_store: Final = refresh_store
        self._denylist: Final = denylist
        self._access_ttl: Final = timedelta(
            seconds=security_config.access_token_ttl_seconds,
        )

    async def run(self, data: ResetPasswordCommand) -> None:
        user_id = await self._email_tokens.consume(data.token, EmailTokenPurpose.RESET)
        user = await self._user_gateway.with_id(user_id)
        if user is None:
            raise InvalidTokenError

        user.change_password(self._hasher.hash(RawPassword(data.new_password)))
        revoked_families = await self._refresh_store.revoke_all_for_user(user_id)
        if revoked_families:
            denied_until = datetime.now(timezone.utc) + self._access_ttl
            for family_id in revoked_families:
                await self._denylist.deny_family(family_id, denied_until)
        await self._transaction.commit()
