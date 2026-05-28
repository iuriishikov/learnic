from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Protocol


class AdminMetric(StrEnum):
    """A time-series metric the admin dashboard can chart.

    Each value maps to a slice of the ``statistics`` event log:

    - ``REGISTRATIONS`` — ``registration`` events, counted.
    - ``ENROLLMENTS`` — ``enrollment`` events, counted.
    - ``ACTIVE_USERS`` — distinct actors of ``site_visit`` events
      per day (the daily-active-users series).
    """

    REGISTRATIONS = "registrations"
    ENROLLMENTS = "enrollments"
    ACTIVE_USERS = "active_users"


@dataclass(slots=True, frozen=True)
class MetricPoint:
    """One bucket of a daily metric series."""

    day: date
    count: int


class AdminMetricsReader(Protocol):
    """Read-side source of admin dashboard time series."""

    async def daily_counts(
        self,
        metric: AdminMetric,
        since: datetime,
    ) -> list[MetricPoint]:
        """Return per-UTC-day counts for ``metric`` from ``since`` onward.

        Sparse: only days that actually have events are returned,
        ascending by day. The caller is responsible for zero-filling
        the gaps across the requested window. ``ACTIVE_USERS`` counts
        distinct actors per day; the others count rows.
        """
        ...
