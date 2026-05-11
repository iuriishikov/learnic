import uuid
from datetime import datetime
from typing import Protocol


class TokenDenylist(Protocol):
    """Family-level instant revocation list for access tokens.

    Stateless access JWTs cannot be revoked by themselves — they live
    out their natural ``exp``. The denylist closes that window: every
    revocation event (logout, "Logout from this device", logout-all,
    password reset) writes the relevant ``family_id`` here for one
    access-TTL window. Access JWTs carry the ``family_id`` they were
    minted with as the ``fid`` claim; the auth path matches against
    this list and rejects compromised tokens on the next request,
    instead of the 20-minute grace window.

    Entries auto-expire at ``now + access_ttl_seconds`` past the
    revocation moment because no token issued earlier can still be
    valid by then. ``cleanup_expired`` reaps them on a schedule so
    the table stays small.
    """

    async def is_family_denied(self, family_id: uuid.UUID) -> bool:
        """Return ``True`` if ``family_id`` has been revoked.

        Access tokens carrying this ``fid`` claim must be rejected
        until the entry expires.
        """
        ...

    async def deny_family(
        self,
        family_id: uuid.UUID,
        expires_at: datetime,
    ) -> None:
        """Mark ``family_id`` as revoked until ``expires_at``.

        ``expires_at`` should be set to ``now + access_ttl`` so the
        denylist row is removed once no access token issued with
        this family could still be valid. Calling repeatedly with a
        fresh ``expires_at`` extends the entry's lifetime in place.
        """
        ...

    async def cleanup_expired(self) -> int:
        """Remove entries whose ``expires_at`` has passed.

        Returns the number of rows removed. Callers are expected to
        run this periodically (e.g. from a scheduled task).
        """
        ...
