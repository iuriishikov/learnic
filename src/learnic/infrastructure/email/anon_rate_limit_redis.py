import logging
from typing import Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.email.anon_rate_limit import (
    AnonymousEmailRateLimiter,
)
from learnic.application.common.errors import (
    AnonymousEmailRateLimitExceededError,
)
from learnic.entities.email_sending.constants import (
    ANON_EMAIL_RATE_LIMIT_WINDOW,
    MAX_ANON_EMAILS_PER_RECIPIENT,
)
from learnic.entities.user.value_objects import normalize_email

_logger = logging.getLogger(__name__)

_KEY_PREFIX: Final = "anon-email-rl:"
_WINDOW_SECONDS: Final = int(ANON_EMAIL_RATE_LIMIT_WINDOW.total_seconds())


class AnonymousEmailRateLimiterRedis(AnonymousEmailRateLimiter):
    """Fixed-window recipient counter backed by Redis ``INCR`` + ``EXPIRE``.

    The first send to a recipient in the window seeds the counter and
    arms the TTL; subsequent sends increment it. Once the count exceeds
    :data:`MAX_ANON_EMAILS_PER_RECIPIENT` the send is refused with HTTP
    429 until the window rolls over.

    Fails **open**: any Redis error is logged and treated as "under the
    cap" so a degraded cache can never lock a real user out of password
    reset. The cap is abuse mitigation, not an authorization boundary.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def check(self, recipient: str) -> None:
        key = f"{_KEY_PREFIX}{normalize_email(recipient)}"
        try:
            count = await self._redis.incr(key)
            if count == 1:
                await self._redis.expire(key, _WINDOW_SECONDS)
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Anon email rate limiter degraded; failing open for %s",
                key,
            )
            return
        if count > MAX_ANON_EMAILS_PER_RECIPIENT:
            raise AnonymousEmailRateLimitExceededError(
                limit=MAX_ANON_EMAILS_PER_RECIPIENT,
                retry_after_seconds=_WINDOW_SECONDS,
            )
