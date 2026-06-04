from datetime import datetime
from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.admin_metrics import (
    AdminMetric,
    AdminMetricsReader,
    MetricPoint,
)
from learnic.entities.statistic.enums import StatisticType
from learnic.infrastructure.persistence.models.product import products_table
from learnic.infrastructure.persistence.models.statistic import (
    statistics_table,
)

# metric -> (event type to slice on, whether to count distinct actors)
_METRIC_SOURCE: Final[dict[AdminMetric, tuple[StatisticType, bool]]] = {
    AdminMetric.REGISTRATIONS: (StatisticType.REGISTRATION, False),
    AdminMetric.ENROLLMENTS: (StatisticType.ENROLLMENT, False),
    AdminMetric.ACTIVE_USERS: (StatisticType.SITE_VISIT, True),
}


class AdminMetricsReaderAlchemy(AdminMetricsReader):
    """Groups ``statistics`` rows into per-UTC-day counts.

    One ``GROUP BY`` over the event type's slice. The day bucket is
    computed at UTC (``timezone('UTC', created_at)::date``) so the
    series does not drift with the server's session timezone — it
    matches the UTC-day bucketing the ``site_visit`` dedup already
    uses.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def daily_counts(
        self,
        metric: AdminMetric,
        since: datetime,
    ) -> list[MetricPoint]:
        if metric is AdminMetric.NEW_PRODUCTS:
            return await self._new_products_daily(since)
        return await self._event_daily(metric, since)

    async def _event_daily(
        self,
        metric: AdminMetric,
        since: datetime,
    ) -> list[MetricPoint]:
        stat_type, distinct_actors = _METRIC_SOURCE[metric]
        day = sa.cast(
            sa.func.timezone("UTC", statistics_table.c.created_at),
            sa.Date,
        ).label("day")
        counter = (
            sa.func.count(sa.distinct(statistics_table.c.actor_id))
            if distinct_actors
            else sa.func.count()
        )
        stmt = (
            # NB: label it ``total`` not ``count`` — a SQLAlchemy ``Row``
            # is tuple-like, so ``row.count`` would resolve to the
            # sequence's ``count()`` method instead of the column value.
            sa.select(day, counter.label("total"))
            .where(
                statistics_table.c.type == stat_type.value,
                statistics_table.c.created_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )
        rows = (await self._session.execute(stmt)).all()
        return [MetricPoint(day=row.day, count=row.total) for row in rows]

    async def _new_products_daily(
        self,
        since: datetime,
    ) -> list[MetricPoint]:
        """Count ``products`` created per UTC day from ``since`` onward.

        There is no product-creation event in the ``statistics`` log, so
        this series comes straight off ``products.created_at``. Every
        product counts the day it was created, regardless of its current
        lifecycle status (draft / published / archived). Same UTC-day
        bucketing and sparse-result contract as :meth:`_event_daily`.
        """
        day = sa.cast(
            sa.func.timezone("UTC", products_table.c.created_at),
            sa.Date,
        ).label("day")
        stmt = (
            sa.select(day, sa.func.count().label("total"))
            .where(products_table.c.created_at >= since)
            .group_by(day)
            .order_by(day)
        )
        rows = (await self._session.execute(stmt)).all()
        return [MetricPoint(day=row.day, count=row.total) for row in rows]
