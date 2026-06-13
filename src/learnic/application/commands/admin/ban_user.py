from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.security.refresh_tokens import (
    RefreshTokenStore,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class BanUserCommand:
    user_id: UserID


@final
class BanUserCommandHandler:
    """Ban a user and terminate every active session they hold.

    Two effects, both required for a ban to stick:

    1. The ``is_banned`` flag blocks future logins
       (``LoginCommandHandler`` checks it).
    2. Every refresh-token family is revoked and added to the family
       denylist, so the access JWTs already in the banned user's
       browser (still valid by ``exp``) are rejected on their next
       request instead of lingering for the full access-token TTL.

    Mirrors :class:`LogoutAllCommandHandler`'s revocation flow.
    Idempotent — re-banning re-revokes any sessions opened since.
    """

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        refresh_store: RefreshTokenStore,
        denylist: TokenDenylist,
        security_config: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._refresh_store: Final = refresh_store
        self._denylist: Final = denylist
        self._access_ttl: Final = timedelta(
            seconds=security_config.access_token_ttl_seconds,
        )

    async def run(self, data: BanUserCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        user.ban()
        revoked_families = await self._refresh_store.revoke_all_for_user(
            data.user_id,
        )
        if revoked_families:
            denied_until = datetime.now(timezone.utc) + self._access_ttl
            for family_id in revoked_families:
                await self._denylist.deny_family(family_id, denied_until)
        await self._transaction.commit()
