from typing import Protocol

from learnic.entities.notification_preferences.models import (
    NotificationPreferences,
)
from learnic.entities.user.models import UserID


class NotificationPreferencesGateway(Protocol):
    """Write-side persistence for :class:`NotificationPreferences`.

    Stored as a single row per user with one boolean column per
    ``(channel, category)`` pair. ``upsert`` is the only write path:
    the settings UI ships the full matrix on every save so we don't
    have to merge partial updates here. First-time saves create the
    row; subsequent saves refresh ``updated_at`` and the toggles.
    """

    async def upsert(self, preferences: NotificationPreferences) -> None: ...

    async def with_user_id(
        self,
        user_id: UserID,
    ) -> NotificationPreferences | None:
        """Fetch the row for ``user_id`` if it has been persisted."""
        ...
