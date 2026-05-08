from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.notifications.reader import NotificationReader
from learnic.application.common.notifications.views import (
    NotificationListPage,
)
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListMyNotificationsQuery:
    actor_id: UserID
    category: NotificationCategory | None
    cursor: str | None
    limit: int


@final
class ListMyNotificationsQueryHandler:
    def __init__(self, reader: NotificationReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: ListMyNotificationsQuery,
    ) -> NotificationListPage:
        return await self._reader.list_for(
            recipient_id=data.actor_id,
            category=data.category,
            cursor=data.cursor,
            limit=data.limit,
        )
