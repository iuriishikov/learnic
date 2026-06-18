from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Final, Protocol

from learnic.entities.user.models import UserID


class EmailTokenPurpose(StrEnum):
    VERIFY = "verify"
    RESET = "reset"


# Lifetime of a VERIFY email token, in seconds. Deliberately a fixed
# code constant rather than an env-tunable setting (unlike the other
# auth TTLs on SecurityConfig): the verification window is a product
# decision, not a per-environment operational knob. Keeping it here as
# the single source of truth removes the env-vs-code drift that once
# let prod silently run 24h while the code default said 1h.
VERIFY_EMAIL_TOKEN_TTL_SECONDS: Final = 60 * 60


@dataclass(slots=True, frozen=True)
class EmailTokenInfo:
    """Metadata for a live email token.

    Returned from :meth:`EmailTokenStore.peek` so callers can branch on
    ``purpose`` without consuming the token. ``user_id`` lets resend
    flows look up the owner.
    """

    user_id: UserID
    purpose: EmailTokenPurpose
    expires_at: datetime


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

    async def peek(self, raw_token: str) -> EmailTokenInfo:
        """Read token metadata without consuming.

        Used by:
        - the unified ``POST /auth/verify-token`` dispatcher to learn
          which ``purpose`` the token was issued for before delegating
          to the matching specialized handler;
        - ``POST /auth/token-status`` to validate a link before
          rendering a form (e.g. password-reset) or before showing the
          generic confirm UI.

        Raises:
            InvalidTokenError: token unknown, expired, or already consumed.
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
