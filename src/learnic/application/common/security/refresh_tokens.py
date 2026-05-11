import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeviceContext:
    """Optional metadata captured at the HTTP boundary for an issuing request.

    Used to attribute a refresh token to the device/location it was
    issued from so the user can later see and revoke their active
    sessions. All fields are nullable because non-browser clients (or
    legacy callers) may not provide them.
    """

    ip_address: str | None = None
    user_agent: str | None = None
    device_label: str | None = None


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
        device: DeviceContext | None = None,
    ) -> IssuedRefreshToken:
        """Issue a new refresh token.

        When ``family_id`` is ``None`` a fresh family is started (used on
        login); otherwise the new token joins an existing family (used
        during rotation). The optional ``device`` is denormalised onto
        the row for later display in the user's active-sessions list.
        """
        ...

    async def rotate(
        self,
        presented: str,
        device: DeviceContext | None = None,
    ) -> IssuedRefreshToken:
        """Rotate ``presented`` into a new refresh token.

        Must implement reuse detection: if ``presented`` is already
        revoked or not the latest token in its family, the whole family
        is revoked and ``InvalidTokenError`` is raised. The new row is
        stamped with ``device`` so the active-sessions view shows the
        most recent location/device the family was seen from.

        Raises:
            InvalidTokenError: token unknown, expired, revoked, or
                reuse detected.
        """
        ...

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        """Revoke every token in ``family_id``."""
        ...

    async def revoke_family_for_user(
        self,
        user_id: UserID,
        family_id: uuid.UUID,
    ) -> bool:
        """Revoke ``family_id`` only if it currently belongs to ``user_id``.

        Returns ``True`` when at least one active row was revoked.
        Returns ``False`` when the family does not exist for that user
        (already revoked, never existed, or owned by someone else) so
        that the caller can translate this into a 404 without leaking
        cross-user existence.
        """
        ...

    async def revoke_all_for_user(self, user_id: UserID) -> set[uuid.UUID]:
        """Revoke every active refresh token for ``user_id``.

        Returns the set of distinct ``family_id`` values that were
        actually flipped to revoked. Empty set when the user already
        had no active sessions. Callers use this to populate the
        family denylist so the matching access JWTs (still valid by
        ``exp``) are rejected on the next request.
        """
        ...

    async def resolve(self, presented: str) -> RefreshTokenRecord | None:
        """Return the record for ``presented`` or ``None`` if unknown.

        Intended for the logout flow where we need the ``family_id``
        associated with the presented token before revoking.
        """
        ...
