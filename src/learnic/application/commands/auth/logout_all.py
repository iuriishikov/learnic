from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import SecurityConfig


@dataclass(slots=True, frozen=True)
class LogoutAllCommand:
    user_id: UserID


@final
class LogoutAllCommandHandler:
    """Revoke every active session for the user and kill in-flight access.

    Each refresh family that was just revoked is also added to the
    family denylist so the matching access JWTs (still valid by
    ``exp``) are rejected on the next request.
    """

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

    async def run(self, data: LogoutAllCommand) -> None:
        revoked_families = await self._refresh_store.revoke_all_for_user(
            data.user_id,
        )
        if revoked_families:
            denied_until = datetime.now(timezone.utc) + self._access_ttl
            for family_id in revoked_families:
                await self._denylist.deny_family(family_id, denied_until)
        await self._transaction.commit()
