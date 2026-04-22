import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RefreshTokenRecord:
    """Server-side state of an issued refresh token."""

    jti: uuid.UUID
    family_id: uuid.UUID
    user_id: UserID
    expires_at: datetime


@dataclass(slots=True, frozen=True)
class IssuedRefreshToken:
    """Raw opaque token plus its stored record."""

    token: str
    record: RefreshTokenRecord


class RefreshTokenStore(Protocol):
    """Opaque refresh tokens with rotation and reuse detection."""

    async def issue(
        self,
        user_id: UserID,
        family_id: uuid.UUID | None = None,
    ) -> IssuedRefreshToken:
        """Issue a new refresh token.

        When ``family_id`` is ``None`` a fresh family is started (used on
        login); otherwise the new token joins an existing family (used
        during rotation).
        """
        ...

    async def rotate(self, presented: str) -> IssuedRefreshToken:
        """Rotate ``presented`` into a new refresh token.

        Must implement reuse detection: if ``presented`` is already
        revoked or not the latest token in its family, the whole family
        is revoked and ``InvalidTokenError`` is raised.

        Raises:
            InvalidTokenError: token unknown, expired, revoked, or
                reuse detected.
        """
        ...

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revoke every token in ``family_id``."""
        ...

    async def revoke_all_for_user(self, user_id: UserID) -> None:
        """Revoke every active refresh token for ``user_id``."""
        ...

    async def resolve(self, presented: str) -> RefreshTokenRecord | None:
        """Return the record for ``presented`` or ``None`` if unknown.

        Intended for the logout flow where we need the ``family_id``
        associated with the presented token before revoking.
        """
        ...
