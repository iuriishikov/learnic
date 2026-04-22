import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist


@dataclass(slots=True, frozen=True)
class LogoutCommand:
    refresh_token: str | None
    access_jti: uuid.UUID | None
    access_expires_at: datetime | None


@final
class LogoutCommandHandler:
    """Revokes the current device's refresh family and denies current jti."""

    def __init__(
        self,
        transaction: Transaction,
        refresh_store: RefreshTokenStore,
        denylist: TokenDenylist,
    ) -> None:
        self._transaction: Final = transaction
        self._refresh_store: Final = refresh_store
        self._denylist: Final = denylist

    async def run(self, data: LogoutCommand) -> None:
        if data.refresh_token is not None:
            record = await self._refresh_store.resolve(data.refresh_token)
            if record is not None:
                await self._refresh_store.revoke_family(record.family_id)
        if data.access_jti is not None and data.access_expires_at is not None:
            await self._denylist.deny(data.access_jti, data.access_expires_at)
        await self._transaction.commit()
