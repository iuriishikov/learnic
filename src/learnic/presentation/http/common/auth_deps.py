import uuid
from dataclasses import dataclass
from datetime import datetime

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


async def authenticate(
    request: Request,
    access_tokens: AccessTokenService,
    denylist: TokenDenylist,
) -> AccessContext:
    """Decode the access cookie and check it isn't denylisted.

    Plain async function (not a FastAPI ``Depends``) — dishka's
    ``FromDishka`` annotations are resolved by the route class, and
    FastAPI's sub-dependency analysis doesn't understand them. Call
    this directly from route handlers with ``FromDishka``-injected
    services.

    Raises:
        InvalidTokenError: cookie missing, malformed, expired or
            denylisted.
    """
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise InvalidTokenError
    payload = access_tokens.decode(token)
    if await denylist.is_denied(payload.jti):
        raise InvalidTokenError
    return AccessContext(
        user_id=payload.user_id,
        jti=payload.jti,
        expires_at=payload.expires_at,
    )
