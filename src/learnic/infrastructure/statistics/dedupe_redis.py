import logging
from typing import Final

from redis.asyncio import Redis
from typing_extensions import override

from learnic.application.common.statistics.dedupe import StatisticsDedupe

_logger = logging.getLogger(__name__)


class StatisticsDedupeRedis(StatisticsDedupe):
    """Redis-backed dedup filter using ``SET NX EX``.

    A successful ``SET key 1 NX EX <window>`` returns ``True`` —
    the key was previously absent, so this caller "won" the
    window and should write. A failed ``SET`` (key already
    present) returns ``False`` — a previous event still holds
    the window, drop this one.

    Any Redis error is logged and converted to ``True`` (fail
    open). Stats are non-critical; a degraded Redis must not
    cause us to silently drop legitimate events.
    """

    def __init__(self, redis: Redis) -> None:
        self._redis: Final = redis

    @override
    async def try_acquire(self, key: str, window_seconds: int) -> bool:
        if window_seconds <= 0:
            return True
        try:
            acquired = await self._redis.set(
                key,
                "1",
                nx=True,
                ex=window_seconds,
            )
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Statistics dedup store failed; failing open for key %s",
                key,
            )
            return True
        return bool(acquired)
