import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.infrastructure.configs import SecurityConfig


@dataclass(slots=True, frozen=True)
class LogoutCommand:
    """Logout the current device.

    ``refresh_token`` resolves to the refresh-token family for the
    cookie that was just sent. ``access_family_id`` is the ``fid``
    claim from the access cookie — used as a fallback when the
    refresh cookie is missing (legacy clients, manual cookie
    deletion) so the access JWT still gets denied immediately.
    """

    refresh_token: str | None
    access_family_id: uuid.UUID | None


@final
class LogoutCommandHandler:
    """Revoke the current device's refresh family + deny it instantly."""

    def __init__(
        self,
        transaction: Transaction,
        refresh_store: RefreshTokenStore,
        denylist: TokenDenylist,
        security_config: SecurityConfig,
    ) -> None:
        self._transaction: Final = transaction
        self._refresh_store: Final = refresh_store
        self._denylist: Final = denylist
        self._access_ttl: Final = timedelta(
            seconds=security_config.access_token_ttl_seconds,
        )

    async def run(self, data: LogoutCommand) -> None:
        family_id: uuid.UUID | None = None
        if data.refresh_token is not None:
            record = await self._refresh_store.resolve(data.refresh_token)
            if record is not None:
                await self._refresh_store.revoke_family(record.family_id)
                family_id = record.family_id
        if family_id is None:
            family_id = data.access_family_id
        if family_id is not None:
            await self._denylist.deny_family(
                family_id,
                datetime.now(timezone.utc) + self._access_ttl,
            )
        await self._transaction.commit()
