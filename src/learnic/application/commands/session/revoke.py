import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import SecurityConfig


@dataclass(slots=True, frozen=True)
class RevokeSessionCommand:
    user_id: UserID
    family_id: uuid.UUID


@final
class RevokeSessionCommandHandler:
    """Revoke a single refresh-token family owned by the caller.

    Presence-check and ownership-check fold into the same UPDATE so
    that a missing or cross-user ``family_id`` produces an
    ``EntityNotFoundError`` (HTTP 404) without leaking which case
    applies. Every successful revocation also writes the family to
    the family denylist for one access-TTL window — that's how every
    access JWT carrying the same ``fid`` claim (the suspect device's
    cookie + any tabs that refreshed off it within the family) gets
    rejected on the next request, instead of living to its natural
    ``exp``.
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

    async def run(self, data: RevokeSessionCommand) -> None:
        revoked = await self._refresh_store.revoke_family_for_user(
            data.user_id,
            data.family_id,
        )
        if not revoked:
            raise EntityNotFoundError(data.family_id)
        await self._denylist.deny_family(
            data.family_id,
            datetime.now(timezone.utc) + self._access_ttl,
        )
        await self._transaction.commit()
