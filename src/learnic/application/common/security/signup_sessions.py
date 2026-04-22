from typing import Protocol

from learnic.entities.user.models import UserID


class SignupSessionStore(Protocol):
    """Short-lived marker that the browser is waiting for verification.

    Used by ``/auth/email-verification/wait`` to auto-login the tab that
    started registration once the user verifies (possibly from another
    device). Security invariant: auto-login only fires when the verify
    request's browser holds the same ``signup_session`` cookie that was
    issued on ``/auth/register``.
    """

    async def issue(self, user_id: UserID, ttl_seconds: int) -> str:
        """Issue a new signup-session token and return its raw form."""
        ...

    async def resolve(self, raw_token: str) -> UserID | None:
        """Return ``user_id`` if ``raw_token`` is live, else ``None``."""
        ...

    async def revoke(self, raw_token: str) -> None:
        """Invalidate ``raw_token`` (no-op if already gone)."""
        ...
