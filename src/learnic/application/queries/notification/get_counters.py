from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.notifications.views import (
    NotificationCounters,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMyNotificationCountersQuery:
    actor_id: UserID


@final
class GetMyNotificationCountersQueryHandler:
    def __init__(self, reader: NotificationReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetMyNotificationCountersQuery,
    ) -> NotificationCounters:
        return await self._reader.counters_for(data.actor_id)
