from enum import StrEnum
from typing import Protocol

from learnic.entities.user.models import UserID


class EmailTokenPurpose(StrEnum):
    VERIFY = "verify"
    RESET = "reset"


class EmailTokenStore(Protocol):
    """Single-use tokens delivered by email (verification, reset)."""

    async def issue(
        self,
        user_id: UserID,
        purpose: EmailTokenPurpose,
        ttl_seconds: int,
    ) -> str:
        """Issue a new token and return its raw form.

        Any previously-active tokens for ``(user_id, purpose)`` are
        invalidated so that a resend supersedes older links.
        """
        ...

    async def consume(
        self,
        raw_token: str,
        purpose: EmailTokenPurpose,
    ) -> UserID:
        """Atomically consume ``raw_token`` and return its ``user_id``.

        Raises:
            InvalidTokenError: token unknown, expired, already consumed,
                or issued for a different purpose.
        """
        ...
