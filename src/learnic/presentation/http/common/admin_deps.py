"""Admin authentication dependency for the presentation layer.

Wraps the standard :class:`Authenticator` with the extra step of
loading the caller and asserting the platform-admin flag, so admin
routes get the same ``await ...authenticate_admin(request)`` ergonomics
the rest of the API gets from ``Authenticator.authenticate``.
"""

from typing import Final, final

from fastapi import Request

from learnic.application.common.errors import NotAdminError
from learnic.application.common.persistence.user import UserGateway
from learnic.presentation.http.common.auth_deps import (
    AccessContext,
    Authenticator,
)


@final
class AdminAuthenticator:
    """Validate the access cookie *and* require an admin caller.

    Routes depend on ``FromDishka[AdminAuthenticator]`` and call
    ``await admin_auth.authenticate_admin(request)``. The extra DB
    round-trip (one ``users`` lookup) is acceptable on the admin
    surface, which is low-traffic by nature.
    """

    def __init__(
        self,
        authenticator: Authenticator,
        user_gateway: UserGateway,
    ) -> None:
        self._authenticator: Final = authenticator
        self._user_gateway: Final = user_gateway

    async def authenticate_admin(self, request: Request) -> AccessContext:
        """Return the caller's context, or refuse non-admins.

        Raises:
            InvalidTokenError: cookie missing, malformed, expired, or
                its refresh-token family is denied (HTTP 401).
            NotAdminError: the caller is authenticated but is not a
                platform administrator (HTTP 403). A user who no
                longer exists is treated the same way.
        """
        ctx = await self._authenticator.authenticate(request)
        user = await self._user_gateway.with_id(ctx.user_id)
        if user is None or not user.is_admin:
            raise NotAdminError(ctx.user_id)
        return ctx
