from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.auth.common import TokenPair
from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.refresh_tokens import (
    DeviceContext,
    RefreshTokenStore,
)
from learnic.application.common.security.signup_sessions import (
    SignupSessionStore,
)


@dataclass(slots=True, frozen=True)
class VerifyWaitCommand:
    signup_session_token: str
    device: DeviceContext | None = None


@dataclass(slots=True, frozen=True)
class VerifyWaitResult:
    """Polling outcome.

    ``ready=False`` means the caller should keep polling; ``ready=True``
    carries the token pair to install as auth cookies.
    """

    ready: bool
    token_pair: TokenPair | None = None


@final
class VerifyWaitCommandHandler:
    """Polling endpoint for the registration tab's auto-login."""

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        signup_sessions: SignupSessionStore,
        access_tokens: AccessTokenService,
        refresh_store: RefreshTokenStore,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._signup_sessions: Final = signup_sessions
        self._access_tokens: Final = access_tokens
        self._refresh_store: Final = refresh_store

    async def run(self, data: VerifyWaitCommand) -> VerifyWaitResult:
        user_id = await self._signup_sessions.resolve(data.signup_session_token)
        if user_id is None:
            raise InvalidTokenError

        user = await self._user_gateway.with_id(user_id)
        if user is None:
            raise InvalidTokenError

        if not user.email_verified:
            return VerifyWaitResult(ready=False)

        refresh = await self._refresh_store.issue(user.oid, device=data.device)
        access = self._access_tokens.issue(user.oid, refresh.record.family_id)
        await self._signup_sessions.revoke(data.signup_session_token)
        await self._transaction.commit()

        return VerifyWaitResult(
            ready=True,
            token_pair=TokenPair(
                access_token=access.token,
                access_expires_at=access.payload.expires_at,
                refresh_token=refresh.token,
                refresh_expires_at=refresh.record.expires_at,
            ),
        )
