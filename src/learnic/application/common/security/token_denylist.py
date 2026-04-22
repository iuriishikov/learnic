import uuid
from datetime import datetime
from typing import Protocol


class TokenDenylist(Protocol):
    """Instant revocation list for access-token ``jti`` claims.

    Only populated on real revocation events (logout, password change,
    admin kill-switch) — entries auto-expire when their original
    ``exp`` passes, so the table stays small.
    """

    async def is_denied(self, jti: uuid.UUID) -> bool:
        """Return ``True`` if this ``jti`` has been revoked."""
        ...

    async def deny(self, jti: uuid.UUID, expires_at: datetime) -> None:
        """Add ``jti`` to the denylist until ``expires_at``."""
        ...

    async def cleanup_expired(self) -> int:
        """Remove entries whose ``expires_at`` is already in the past.

        Returns the number of rows removed. Callers are expected to run
        this periodically (e.g. from a scheduled task).
        """
        ...
