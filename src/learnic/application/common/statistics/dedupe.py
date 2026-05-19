from typing import Protocol


class StatisticsDedupe(Protocol):
    """Side-channel for deduplicating repeated statistic events.

    The dedup filter is keyed by an opaque string the spec
    computes from the event (typically a tuple of actor + target).
    Implementations are expected to hold the key for the supplied
    TTL and return ``False`` for any subsequent attempt within the
    window — that's the "stitching" semantic callers rely on.

    Failure mode is **fail-open**: any infrastructure error (Redis
    timeout, network glitch) MUST return ``True`` so a degraded
    dedup store never blocks legitimate writes. Stats accept a
    duplicate now and then in exchange for never losing events.
    """

    async def try_acquire(self, key: str, window_seconds: int) -> bool:
        """Acquire the dedup window for ``key``.

        Returns:
            ``True`` if this is the first acquisition within the
            ``window_seconds`` — the caller should proceed with
            the write. ``False`` if a previous acquisition still
            holds the window — the caller should drop the event.
        """
        ...
