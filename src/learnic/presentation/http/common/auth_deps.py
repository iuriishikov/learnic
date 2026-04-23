import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from fastapi import Request

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.cookies import ACCESS_COOKIE


@dataclass(slots=True, frozen=True)
class AccessContext:
    user_id: UserID
    jti: uuid.UUID
    expires_at: datetime


@final
class Authenticator:
    """Injectable façade for reading and validating the access cookie.

    Routes depend on ``FromDishka[Authenticator]`` and call
    ``await auth.authenticate(request)`` instead of juggling
    ``AccessTokenService`` + ``TokenDenylist`` by hand. Kept in the
    presentation layer because it knows about FastAPI's ``Request``.
    """

    def __init__(
        self,
        access_tokens: AccessTokenService,
        denylist: TokenDenylist,
    ) -> None:
        self._access_tokens: Final = access_tokens
        self._denylist: Final = denylist

    async def authenticate(self, request: Request) -> AccessContext:
        """Decode the access cookie and check it isn't denylisted.

        Raises:
            InvalidTokenError: cookie missing, malformed, expired or
                denylisted.
        """
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise InvalidTokenError
        payload = self._access_tokens.decode(token)
        if await self._denylist.is_denied(payload.jti):
            raise InvalidTokenError
        return AccessContext(
            user_id=payload.user_id,
            jti=payload.jti,
            expires_at=payload.expires_at,
        )
