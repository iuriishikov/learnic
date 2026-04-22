import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import jwt
from typing_extensions import override

from learnic.application.common.errors import InvalidTokenError
from learnic.application.common.security.access_tokens import (
    AccessTokenPayload,
    AccessTokenService,
    IssuedAccessToken,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.configs import SecurityConfig

_ALGORITHM: Final = "HS256"


class JwtAccessTokenService(AccessTokenService):
    """HS256 JWT access-token service.

    The only claims we rely on are ``sub`` (user id), ``jti``, ``iat``
    and ``exp`` — anything else a future upgrade adds stays opaque to
    callers.
    """

    def __init__(self, config: SecurityConfig) -> None:
        self._secret: Final = config.jwt_secret
        self._ttl: Final = timedelta(
            seconds=config.access_token_ttl_seconds,
        )

    @override
    def issue(self, user_id: UserID) -> IssuedAccessToken:
        now = datetime.now(timezone.utc)
        expires_at = now + self._ttl
        jti = uuid.uuid4()
        payload: dict[str, Any] = {
            "sub": str(user_id),
            "jti": str(jti),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self._secret, algorithm=_ALGORITHM)
        return IssuedAccessToken(
            token=token,
            payload=AccessTokenPayload(
                user_id=user_id,
                jti=jti,
                expires_at=expires_at,
            ),
        )

    @override
    def decode(self, token: str) -> AccessTokenPayload:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError from exc
        try:
            return AccessTokenPayload(
                user_id=UserID(uuid.UUID(claims["sub"])),
                jti=uuid.UUID(claims["jti"]),
                expires_at=datetime.fromtimestamp(claims["exp"], tz=timezone.utc),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidTokenError from exc
