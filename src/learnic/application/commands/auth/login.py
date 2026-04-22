from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.auth.common import TokenPair
from learnic.application.common.errors import (
    EmailNotVerifiedError,
    InvalidCredentialsError,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.passwords import PasswordHasher
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.entities.user.value_objects import RawPassword


@dataclass(slots=True, frozen=True)
class LoginCommand:
    email: str
    password: str


@final
class LoginCommandHandler:
    def __init__(
        self,
        user_gateway: UserGateway,
        hasher: PasswordHasher,
        access_tokens: AccessTokenService,
        refresh_store: RefreshTokenStore,
    ) -> None:
        self._user_gateway: Final = user_gateway
        self._hasher: Final = hasher
        self._access_tokens: Final = access_tokens
        self._refresh_store: Final = refresh_store

    async def run(self, data: LoginCommand) -> TokenPair:
        user = await self._user_gateway.with_email(data.email)
        if user is None:
            raise InvalidCredentialsError
        if not self._hasher.verify(RawPassword(data.password), user.password_hash):
            raise InvalidCredentialsError
        if not user.email_verified:
            raise EmailNotVerifiedError

        access = self._access_tokens.issue(user.oid)
        refresh = await self._refresh_store.issue(user.oid)
        return TokenPair(
            access_token=access.token,
            access_expires_at=access.payload.expires_at,
            refresh_token=refresh.token,
            refresh_expires_at=refresh.record.expires_at,
        )
