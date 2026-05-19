import logging
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from typing_extensions import override

from learnic.application.common.statistics.collector import (
    StatisticsCollector,
)
from learnic.entities.statistic.models import Statistic
from learnic.infrastructure.persistence.adapters.statistic import (
    StatisticMapperAlchemy,
)
from learnic.infrastructure.statistics.specs._spec import (
    StatisticTypeRegistry,
)

_logger = logging.getLogger(__name__)


class StatisticsCollectorAlchemy(StatisticsCollector):
    """Inline-write implementation of :class:`StatisticsCollector`.

    Opens its own short-lived session per call rather than
    sharing the caller's request session — this is intentional and
    has two consequences worth knowing:

    - The collector works from anywhere, including query handlers
      and middleware, which have no transaction of their own to
      commit on.
    - A statistic write is **not** part of the caller's
      transaction. If the surrounding request rolls back, the
      stat row is still committed. This is the right tradeoff
      for analytics (better to log the event than to lose it),
      but means the collector is unsuitable for cases where
      atomicity with business state is required — those should
      use :class:`StatisticGateway` directly inside the caller's
      transaction.

    Failures are logged and swallowed. A failing stat write must
    never propagate into a 500 on a user-facing endpoint that
    only wanted to fire-and-forget an event. Callers that need to
    react to write failures use the gateway directly.

    Switching to an enqueue-and-flush path (TaskIQ) is a single
    DI binding swap — the Protocol is identical, callers are
    unaffected.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        type_registry: StatisticTypeRegistry,
    ) -> None:
        self._maker: Final = session_maker
        self._types: Final = type_registry

    @override
    async def record(self, statistic: Statistic) -> None:
        try:
            async with self._maker() as session, session.begin():
                gateway = StatisticMapperAlchemy(session, self._types)
                await gateway.add(statistic)
        except Exception:  # noqa: BLE001
            _logger.exception(
                "Failed to record statistic %s of type %s",
                statistic.oid,
                statistic.type.value,
            )
