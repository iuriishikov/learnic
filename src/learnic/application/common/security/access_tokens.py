import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AccessTokenPayload:
    """Decoded access-token fields needed by the HTTP layer."""

    user_id: UserID
    jti: uuid.UUID
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class IssuedAccessToken:
    """Raw JWT string plus its decoded payload."""

    token: str
    payload: AccessTokenPayload


class AccessTokenService(Protocol):
    """Issues and decodes short-lived access JWTs."""

    def issue(self, user_id: UserID) -> IssuedAccessToken:
        """Issue a new access token for ``user_id``."""
        ...

    def decode(self, token: str) -> AccessTokenPayload:
        """Decode and validate ``token``.

        Raises:
            InvalidTokenError: token is malformed, expired or signature
                does not match.
        """
        ...
