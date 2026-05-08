import uuid
from unittest.mock import AsyncMock

from learnic.application.queries.presence.get_user_presence import (
    GetUserPresenceQuery,
    GetUserPresenceQueryHandler,
)
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


async def test_returns_online_when_tracker_says_so(
    fake_presence_tracker: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    fake_presence_tracker.is_online.return_value = True
    handler = GetUserPresenceQueryHandler(tracker=fake_presence_tracker)

    view = await handler.run(GetUserPresenceQuery(user_id=user_id))

    assert view.user_id == user_id
    assert view.status is PresenceStatus.ONLINE
    fake_presence_tracker.is_online.assert_awaited_once_with(user_id)


async def test_returns_offline_when_tracker_says_so(
    fake_presence_tracker: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    fake_presence_tracker.is_online.return_value = False
    handler = GetUserPresenceQueryHandler(tracker=fake_presence_tracker)

    view = await handler.run(GetUserPresenceQuery(user_id=user_id))

    assert view.user_id == user_id
    assert view.status is PresenceStatus.OFFLINE
