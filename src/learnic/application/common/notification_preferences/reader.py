from typing import Final, Protocol, final

from learnic.application.common.notification_preferences.gateway import (
    NotificationPreferencesGateway,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.notification_preferences.models import (
    NotificationPreferences,
)
from learnic.entities.user.models import UserID


class NotificationPreferencesReader(Protocol):
    """Read-side façade returning a fully-materialised preferences object.

    Wraps :class:`NotificationPreferencesGateway` so the publisher
    never has to think about the missing-row case — the reader
    falls back to :meth:`NotificationPreferences.defaults_for` so
    every check is total.
    """

    async def for_user(
        self,
        user_id: UserID,
    ) -> NotificationPreferences: ...

    async def is_channel_enabled(
        self,
        user_id: UserID,
        channel: NotificationChannel,
        category: NotificationCategory,
    ) -> bool: ...


@final
class NotificationPreferencesReaderService(NotificationPreferencesReader):
    """Default reader: gateway lookup + defaults fallback."""

    def __init__(self, gateway: NotificationPreferencesGateway) -> None:
        self._gateway: Final = gateway

    async def for_user(
        self,
        user_id: UserID,
    ) -> NotificationPreferences:
        stored = await self._gateway.with_user_id(user_id)
        if stored is not None:
            return stored
        return NotificationPreferences.defaults_for(user_id)

    async def is_channel_enabled(
        self,
        user_id: UserID,
        channel: NotificationChannel,
        category: NotificationCategory,
    ) -> bool:
        prefs = await self.for_user(user_id)
        return prefs.is_enabled(channel, category)
