from datetime import datetime, timezone
from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.notification_preferences.gateway import (
    NotificationPreferencesGateway,
)
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.notification_preferences.models import (
    NotificationPreferences,
)
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.notification_preferences import (
    notification_preferences_table,
)


_PUSH_COLUMNS: Final[dict[NotificationCategory, str]] = {
    NotificationCategory.TEACHING: "push_teaching",
    NotificationCategory.LEARNING: "push_learning",
    NotificationCategory.SECURITY: "push_security",
    NotificationCategory.FILES: "push_files",
    NotificationCategory.JOBS: "push_jobs",
    NotificationCategory.OTHER: "push_other",
}

_EMAIL_COLUMNS: Final[dict[NotificationCategory, str]] = {
    NotificationCategory.TEACHING: "email_teaching",
    NotificationCategory.LEARNING: "email_learning",
    NotificationCategory.SECURITY: "email_security",
    NotificationCategory.FILES: "email_files",
    NotificationCategory.JOBS: "email_jobs",
    NotificationCategory.OTHER: "email_other",
}


class NotificationPreferencesMapperAlchemy(NotificationPreferencesGateway):
    """Postgres adapter for the wide-column preferences row.

    Fields are denormalised — one boolean per ``(channel, category)``
    pair — so reads are single-row and writes are a trivial upsert.
    The dict ↔ row translation lives here because the entity
    intentionally exposes a category-keyed dict for ergonomic
    publisher-side checks.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def upsert(self, preferences: NotificationPreferences) -> None:
        now = datetime.now(timezone.utc)
        values: dict[str, Any] = {
            "user_id": preferences.user_id,
            "created_at": now,
            "updated_at": now,
        }
        for category, column in _PUSH_COLUMNS.items():
            values[column] = preferences.push.get(category, True)
        for category, column in _EMAIL_COLUMNS.items():
            values[column] = preferences.email.get(category, False)

        stmt = pg_insert(notification_preferences_table).values(**values)
        update_set = {
            column: stmt.excluded[column]
            for column in (
                *_PUSH_COLUMNS.values(),
                *_EMAIL_COLUMNS.values(),
            )
        }
        update_set["updated_at"] = stmt.excluded.updated_at
        stmt = stmt.on_conflict_do_update(
            index_elements=[notification_preferences_table.c.user_id],
            set_=update_set,
        )
        await self._session.execute(stmt)

    @override
    async def with_user_id(
        self,
        user_id: UserID,
    ) -> NotificationPreferences | None:
        row = (
            await self._session.execute(
                sa.select(notification_preferences_table).where(
                    notification_preferences_table.c.user_id == user_id,
                ),
            )
        ).one_or_none()
        if row is None:
            return None
        push = {
            category: bool(getattr(row, column))
            for category, column in _PUSH_COLUMNS.items()
        }
        email = {
            category: bool(getattr(row, column))
            for category, column in _EMAIL_COLUMNS.items()
        }
        return NotificationPreferences(
            user_id=UserID(row.user_id),
            push=push,
            email=email,
        )
