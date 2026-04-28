import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from fastapi import Request
from fastapi.security import APIKeyCookie

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.access_tokens import (
    AccessTokenService,
)
from learnic.application.common.security.token_denylist import TokenDenylist
from learnic.entities.user.models import UserID
from learnic.presentation.http.common.cookies import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    SIGNUP_SESSION_COOKIE,
)

access_cookie_scheme: Final = APIKeyCookie(
    name=ACCESS_COOKIE,
    scheme_name="accessCookie",
    description=(
        "HttpOnly cookie issued by `POST /auth/login` (or by "
        "`GET /auth/email-verification/wait` once the email is "
        "confirmed). Sent automatically by browsers on every request "
        "to a protected endpoint."
    ),
    auto_error=False,
)

refresh_cookie_scheme: Final = APIKeyCookie(
    name=REFRESH_COOKIE,
    scheme_name="refreshCookie",
    description=(
        "HttpOnly cookie scoped to `/auth/refresh`. Sent automatically "
        "by browsers when calling `POST /auth/refresh` or "
        "`POST /auth/logout`."
    ),
    auto_error=False,
)

signup_session_cookie_scheme: Final = APIKeyCookie(
    name=SIGNUP_SESSION_COOKIE,
    scheme_name="signupSessionCookie",
    description=(
        "HttpOnly cookie scoped to `/auth`. Issued by "
        "`POST /auth/register` and consumed by "
        "`GET /auth/email-verification/wait` to auto-login the same "
        "browser tab once the user clicks the verification link."
    ),
    auto_error=False,
)


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
