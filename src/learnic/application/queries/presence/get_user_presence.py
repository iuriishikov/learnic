from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.presence.tracker import PresenceTracker
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserPresenceQuery:
    user_id: UserID


@dataclass(slots=True, frozen=True)
class UserPresenceView:
    user_id: UserID
    status: PresenceStatus


@final
class GetUserPresenceQueryHandler:
    def __init__(self, tracker: PresenceTracker) -> None:
        self._tracker: Final = tracker

    async def run(self, data: GetUserPresenceQuery) -> UserPresenceView:
        is_online = await self._tracker.is_online(data.user_id)
        status = PresenceStatus.ONLINE if is_online else PresenceStatus.OFFLINE
        return UserPresenceView(user_id=data.user_id, status=status)
