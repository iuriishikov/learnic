from unittest.mock import AsyncMock

from learnic.application.common.persistence.admin_stats import AdminStatsView
from learnic.application.queries.admin.get_stats import (
    GetAdminStatsQuery,
    GetAdminStatsQueryHandler,
)


async def test_get_stats_returns_reader_snapshot() -> None:
    view = AdminStatsView(
        total_users=10,
        banned_users=1,
        admin_users=2,
        total_courses=5,
        draft_courses=2,
        published_courses=3,
        archived_courses=0,
        total_enrollments=42,
        active_enrollments=40,
        dau=7,
        mau=25,
    )
    reader = AsyncMock()
    reader.collect = AsyncMock(return_value=view)

    handler = GetAdminStatsQueryHandler(reader=reader)
    result = await handler.run(GetAdminStatsQuery())

    assert result is view
    reader.collect.assert_awaited_once()
