import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from fastapi import Request, WebSocket
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

_logger = logging.getLogger(__name__)

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
    family_id: uuid.UUID | None = None


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
        """Decode the access cookie and check its family isn't denied.

        Raises:
            InvalidTokenError: cookie missing, malformed, expired, or
                its refresh-token family is in the family denylist
                (logout, "Logout from this device", logout-all,
                password reset).
        """
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            raise InvalidTokenError
        payload = self._access_tokens.decode(token)
        if payload.family_id is not None and await self._denylist.is_family_denied(
            payload.family_id
        ):
            raise InvalidTokenError
        return AccessContext(
            user_id=payload.user_id,
            jti=payload.jti,
            family_id=payload.family_id,
            expires_at=payload.expires_at,
        )

    async def authenticate_optional(
        self,
        request: Request,
    ) -> AccessContext | None:
        """Decode the access cookie if present; never raise.

        Used by side-effect endpoints that serve both anonymous
        and authenticated callers — typically public reads that
        record a per-actor analytics event when the caller is
        signed in. Three outcomes:

        - **No cookie** → ``None`` (anonymous caller, no event).
        - **Cookie valid** → :class:`AccessContext`.
        - **Cookie malformed / expired / denied** → ``None``,
          logged at debug. The request still serves the public
          payload; the anonymous degradation is intentional so
          a stale cookie never breaks a public read.

        For protected endpoints continue using
        :meth:`authenticate` — silent fallback there is a
        security bug, not a feature.
        """
        token = request.cookies.get(ACCESS_COOKIE)
        if not token:
            return None
        try:
            payload = self._access_tokens.decode(token)
        except InvalidTokenError:
            _logger.debug("Optional auth: token decode failed")
            return None
        if payload.family_id is not None and await self._denylist.is_family_denied(
            payload.family_id,
        ):
            _logger.debug("Optional auth: family denied")
            return None
        return AccessContext(
            user_id=payload.user_id,
            jti=payload.jti,
            family_id=payload.family_id,
            expires_at=payload.expires_at,
        )

    async def authenticate_websocket(
        self,
        websocket: WebSocket,
    ) -> AccessContext:
        """Authenticate a WebSocket handshake via the access cookie.

        Browsers attach the same HttpOnly cookies to WS handshakes that
        they send on HTTP requests, so the validation logic mirrors
        :meth:`authenticate` against ``websocket.cookies`` instead of
        ``request.cookies``. A separate method is intentional — keeps
        the existing HTTP signature stable.

        Raises:
            InvalidTokenError: cookie missing, malformed, expired, or
                its refresh-token family is in the family denylist.
        """
        token = websocket.cookies.get(ACCESS_COOKIE)
        if not token:
            raise InvalidTokenError
        payload = self._access_tokens.decode(token)
        if payload.family_id is not None and await self._denylist.is_family_denied(
            payload.family_id
        ):
            raise InvalidTokenError
        return AccessContext(
            user_id=payload.user_id,
            jti=payload.jti,
            family_id=payload.family_id,
            expires_at=payload.expires_at,
        )
