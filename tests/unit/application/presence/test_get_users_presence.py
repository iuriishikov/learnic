import uuid
from unittest.mock import AsyncMock

from learnic.application.queries.presence.get_users_presence import (
    GetUsersPresenceQuery,
    GetUsersPresenceQueryHandler,
)
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


async def test_returns_per_user_status_in_input_order(
    fake_presence_tracker: AsyncMock,
) -> None:
    user_a = UserID(uuid.uuid4())
    user_b = UserID(uuid.uuid4())
    user_c = UserID(uuid.uuid4())
    fake_presence_tracker.filter_online.return_value = {user_a, user_c}

    handler = GetUsersPresenceQueryHandler(tracker=fake_presence_tracker)
    views = await handler.run(
        GetUsersPresenceQuery(user_ids=[user_a, user_b, user_c]),
    )

    assert [v.user_id for v in views] == [user_a, user_b, user_c]
    assert [v.status for v in views] == [
        PresenceStatus.ONLINE,
        PresenceStatus.OFFLINE,
        PresenceStatus.ONLINE,
    ]


async def test_empty_input_returns_empty_list(
    fake_presence_tracker: AsyncMock,
) -> None:
    handler = GetUsersPresenceQueryHandler(tracker=fake_presence_tracker)

    views = await handler.run(GetUsersPresenceQuery(user_ids=[]))

    assert views == []


async def test_all_offline_when_tracker_returns_empty(
    fake_presence_tracker: AsyncMock,
) -> None:
    user_a = UserID(uuid.uuid4())
    user_b = UserID(uuid.uuid4())
    fake_presence_tracker.filter_online.return_value = set()

    handler = GetUsersPresenceQueryHandler(tracker=fake_presence_tracker)
    views = await handler.run(
        GetUsersPresenceQuery(user_ids=[user_a, user_b]),
    )

    assert all(v.status is PresenceStatus.OFFLINE for v in views)
