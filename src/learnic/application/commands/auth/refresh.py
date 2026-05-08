from dataclasses import dataclass
from typing import Final, final

from learnic.application.commands.auth.common import TokenPair
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.refresh_tokens import (
    DeviceContext,
    RefreshTokenStore,
)


@dataclass(slots=True, frozen=True)
class RefreshCommand:
    refresh_token: str
    device: DeviceContext | None = None


@final
class RefreshCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        access_tokens: AccessTokenService,
        refresh_store: RefreshTokenStore,
    ) -> None:
        self._transaction: Final = transaction
        self._access_tokens: Final = access_tokens
        self._refresh_store: Final = refresh_store

    async def run(self, data: RefreshCommand) -> TokenPair:
        refresh = await self._refresh_store.rotate(
            data.refresh_token,
            device=data.device,
        )
        access = self._access_tokens.issue(refresh.record.user_id)
        await self._transaction.commit()
        return TokenPair(
            access_token=access.token,
            access_expires_at=access.payload.expires_at,
            refresh_token=refresh.token,
            refresh_expires_at=refresh.record.expires_at,
        )
