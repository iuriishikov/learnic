from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def fake_presence_tracker() -> AsyncMock:
    tracker = AsyncMock()
    tracker.mark_online = AsyncMock()
    tracker.mark_offline = AsyncMock()
    tracker.heartbeat = AsyncMock()
    tracker.is_online = AsyncMock(return_value=False)
    tracker.filter_online = AsyncMock(return_value=set())
    return tracker
