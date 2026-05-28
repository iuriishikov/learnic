from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Final, final

from learnic.application.common.persistence.admin_metrics import (
    AdminMetric,
    AdminMetricsReader,
    MetricPoint,
)

METRICS_MIN_DAYS: Final = 1
METRICS_DEFAULT_DAYS: Final = 30
METRICS_MAX_DAYS: Final = 366


@dataclass(slots=True, frozen=True)
class GetAdminMetricSeriesQuery:
    metric: AdminMetric
    days: int


@dataclass(slots=True, frozen=True)
class AdminMetricSeries:
    """A dense daily series for one metric over the requested window."""

    metric: AdminMetric
    points: list[MetricPoint]


@final
class GetAdminMetricSeriesQueryHandler:
    """Return a zero-filled daily series for an admin metric.

    The window is the last ``days`` UTC calendar days ending today
    (inclusive). The reader returns only days with events; this
    handler fills the gaps so the SPA always gets exactly ``days``
    points in ascending order — straight to a chart, no client-side
    gap handling.
    """

    def __init__(self, reader: AdminMetricsReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetAdminMetricSeriesQuery) -> AdminMetricSeries:
        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=data.days - 1)
        since = datetime.combine(start, time.min, tzinfo=timezone.utc)

        raw = await self._reader.daily_counts(data.metric, since)
        counts = {point.day: point.count for point in raw}

        points = [
            MetricPoint(
                day=start + timedelta(days=offset),
                count=counts.get(start + timedelta(days=offset), 0),
            )
            for offset in range(data.days)
        ]
        return AdminMetricSeries(metric=data.metric, points=points)
