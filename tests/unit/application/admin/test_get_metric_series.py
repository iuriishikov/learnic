from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from learnic.application.common.persistence.admin_metrics import (
    AdminMetric,
    MetricPoint,
)
from learnic.application.queries.admin.get_metric_series import (
    GetAdminMetricSeriesQuery,
    GetAdminMetricSeriesQueryHandler,
)


async def test_series_is_dense_zero_filled_and_window_bounded() -> None:
    today = datetime.now(timezone.utc).date()
    inside = today - timedelta(days=3)
    outside = today - timedelta(days=99)  # before the 7-day window

    reader = AsyncMock()
    reader.daily_counts = AsyncMock(
        return_value=[
            MetricPoint(day=inside, count=4),
            MetricPoint(day=today, count=9),
            MetricPoint(day=outside, count=100),
        ],
    )

    handler = GetAdminMetricSeriesQueryHandler(reader=reader)
    result = await handler.run(
        GetAdminMetricSeriesQuery(metric=AdminMetric.ENROLLMENTS, days=7),
    )

    assert result.metric is AdminMetric.ENROLLMENTS
    # dense: exactly `days` points, ascending consecutive days, last is today
    assert len(result.points) == 7
    assert result.points[-1].day == today
    assert result.points[0].day == today - timedelta(days=6)
    for i in range(1, 7):
        assert result.points[i].day == result.points[i - 1].day + timedelta(
            days=1,
        )
    # in-window values land on the right day; gaps are zero; the
    # out-of-window point is ignored entirely.
    by_day = {p.day: p.count for p in result.points}
    assert by_day[inside] == 4
    assert by_day[today] == 9
    assert sum(p.count for p in result.points) == 13

    # reader queried from the start of the window at UTC midnight.
    metric_arg, since_arg = reader.daily_counts.await_args.args
    assert metric_arg is AdminMetric.ENROLLMENTS
    assert since_arg == datetime.combine(
        today - timedelta(days=6),
        datetime.min.time(),
        tzinfo=timezone.utc,
    )
