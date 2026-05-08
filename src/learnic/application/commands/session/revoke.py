import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RevokeSessionCommand:
    user_id: UserID
    family_id: uuid.UUID
    current_access_jti: uuid.UUID | None = None
    current_access_expires_at: datetime | None = None


@final
class RevokeSessionCommandHandler:
    """Revoke a single refresh-token family owned by the caller.

    The presence-check and ownership-check are folded into the same UPDATE
    so that a missing or cross-user ``family_id`` produces an
    ``EntityNotFoundError`` (HTTP 404) without leaking which case applies.
    When the caller revokes the session they are *currently using* (e.g.
    "Sign out this device"), the in-flight access JTI is added to the
    denylist so the access cookie cannot outlive the refresh family.
    """

    def __init__(
        self,
        transaction: Transaction,
        refresh_store: RefreshTokenStore,
        denylist: TokenDenylist,
    ) -> None:
        self._transaction: Final = transaction
        self._refresh_store: Final = refresh_store
        self._denylist: Final = denylist

    async def run(self, data: RevokeSessionCommand) -> None:
        revoked = await self._refresh_store.revoke_family_for_user(
            data.user_id,
            data.family_id,
        )
        if not revoked:
            raise EntityNotFoundError(data.family_id)
        if (
            data.current_access_jti is not None
            and data.current_access_expires_at is not None
        ):
            await self._denylist.deny(
                data.current_access_jti,
                data.current_access_expires_at,
            )
        await self._transaction.commit()
