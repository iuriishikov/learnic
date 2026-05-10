from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.notification_preferences.reader import (
    NotificationPreferencesReader,
)
from learnic.entities.notification_preferences.models import (
    NotificationPreferences,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMyNotificationPreferencesQuery:
    actor_id: UserID


@final
class GetMyNotificationPreferencesQueryHandler:
    """Return the caller's preferences with defaults applied.

    Surfaces the matrix the settings UI renders — every category,
    every channel, with stored values where present and defaults
    otherwise. Callers never see ``None``: if the user has never
    saved their preferences, the reader fabricates the default row
    so the UI has a complete picture from the first render.
    """

    def __init__(self, reader: NotificationPreferencesReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetMyNotificationPreferencesQuery,
    ) -> NotificationPreferences:
        return await self._reader.for_user(data.actor_id)
