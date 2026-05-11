import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AccessTokenPayload:
    """Decoded access-token fields needed by the HTTP layer.

    ``family_id`` binds the access token to the refresh-token family
    that produced it (login or rotation). It is the lever for
    "revoke this device" flows: revoking a family adds it to the
    family denylist so the matching access tokens stop validating
    immediately, rather than living out their natural ``exp``.
    Older tokens minted before this claim landed decode with
    ``family_id=None`` and skip the family check — they will rotate
    out within one access-TTL window.
    """

    user_id: UserID
    jti: uuid.UUID
    expires_at: datetime
    family_id: uuid.UUID | None = None


@dataclass(slots=True, frozen=True)
class IssuedAccessToken:
    """Raw JWT string plus its decoded payload."""

    token: str
    payload: AccessTokenPayload


class AccessTokenService(Protocol):
    """Issues and decodes short-lived access JWTs."""

    def issue(
        self,
        user_id: UserID,
        family_id: uuid.UUID,
    ) -> IssuedAccessToken:
        """Issue a new access token bound to a refresh-token family.

        ``family_id`` lands as a JWT claim and surfaces in
        :class:`AccessTokenPayload`. The auth path uses it to enforce
        family-level revocations against the denylist.
        """
        ...

    def decode(self, token: str) -> AccessTokenPayload:
        """Decode and validate ``token``.

        Raises:
            InvalidTokenError: token is malformed, expired or signature
                does not match.
        """
        ...
