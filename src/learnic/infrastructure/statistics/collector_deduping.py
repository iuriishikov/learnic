import logging
from typing import Final

from typing_extensions import override

from learnic.application.common.statistics.collector import (
    StatisticsCollector,
)
from learnic.application.common.statistics.dedupe import StatisticsDedupe
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.statistics.specs._spec import (
    StatisticTypeRegistry,
)

_logger = logging.getLogger(__name__)


class DedupingStatisticsCollector(StatisticsCollector):
    """Decorator that drops repeated events from the same actor.

    Asks the per-type spec for a dedup key + window; if
    :class:`StatisticsDedupe` reports a previous event within the
    window still owns the slot, the event is silently dropped.
    Otherwise, delegates to the wrapped collector.

    The decision is per-type because what counts as a "duplicate"
    is type-specific (same profile, same product, same lesson,
    …). All key-shape knowledge lives in the spec — adding a new
    statistic type therefore needs no change here.

    Specs that opt out of dedup return ``None`` from
    :meth:`dedupe_key` or declare ``dedupe_window_seconds = 0``;
    those events bypass the filter and always reach the inner
    collector.
    """

    def __init__(
        self,
        inner: StatisticsCollector,
        dedupe: StatisticsDedupe,
        type_registry: StatisticTypeRegistry,
    ) -> None:
        self._inner: Final = inner
        self._dedupe: Final = dedupe
        self._types: Final = type_registry

    @override
    async def record(self, statistic: Statistic) -> None:
        spec = self._types.by_details_type(type(statistic.details))
        window = spec.dedupe_window_seconds
        key = spec.dedupe_key(statistic, statistic.details) if window > 0 else None
        if key is not None:
            acquired = await self._dedupe.try_acquire(key, window)
            if not acquired:
                _logger.debug(
                    "Statistic %s dropped by dedup window (key=%s)",
                    statistic.type.value,
                    key,
                )
                return
        await self._inner.record(statistic)
