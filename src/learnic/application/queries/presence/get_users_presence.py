from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.presence.tracker import PresenceTracker
from learnic.application.queries.presence.get_user_presence import (
    UserPresenceView,
)
from learnic.entities.presence.value_objects import PresenceStatus
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUsersPresenceQuery:
    user_ids: list[UserID]


@final
class GetUsersPresenceQueryHandler:
    def __init__(self, tracker: PresenceTracker) -> None:
        self._tracker: Final = tracker

    async def run(
        self,
        data: GetUsersPresenceQuery,
    ) -> list[UserPresenceView]:
        online = await self._tracker.filter_online(data.user_ids)
        return [
            UserPresenceView(
                user_id=user_id,
                status=(
                    PresenceStatus.ONLINE
                    if user_id in online
                    else PresenceStatus.OFFLINE
                ),
            )
            for user_id in data.user_ids
        ]
