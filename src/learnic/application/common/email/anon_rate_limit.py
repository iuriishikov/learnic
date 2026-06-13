from typing import Protocol


class AnonymousEmailRateLimiter(Protocol):
    """Recipient-keyed abuse cap for unauthenticated email endpoints.

    The password-reset request, verification resend, and registration
    flows send transactional email without an authenticated actor, so
    the per-user :class:`EmailSendRateLimiter` cannot key them. This
    limiter caps how many such emails may target one recipient address
    within a rolling window, blunting inbox-flooding / email-bombing.

    Implementations are expected to be best-effort: an infrastructure
    failure (e.g. Redis down) should **fail open** rather than block a
    legitimate user from resetting their password.
    """

    async def check(self, recipient: str) -> None:
        """Record one send to ``recipient`` and refuse if over the cap.

        Args:
            recipient: Destination email address. Implementations
                normalize it (trim + lowercase) so casing variants
                share a bucket.

        Raises:
            AnonymousEmailRateLimitExceededError: ``recipient`` has
                already received the maximum number of unauthenticated
                emails within the window; surfaces as HTTP 429.
        """
        ...
