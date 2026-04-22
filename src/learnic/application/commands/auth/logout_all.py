from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class LogoutAllCommand:
    user_id: UserID


@final
class LogoutAllCommandHandler:
    """Revokes every active refresh session for the given user."""

    def __init__(
        self,
        transaction: Transaction,
        refresh_store: RefreshTokenStore,
    ) -> None:
        self._transaction: Final = transaction
        self._refresh_store: Final = refresh_store

    async def run(self, data: LogoutAllCommand) -> None:
        await self._refresh_store.revoke_all_for_user(data.user_id)
        await self._transaction.commit()
