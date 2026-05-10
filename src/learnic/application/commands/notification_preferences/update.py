from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.notification_preferences.gateway import (
    NotificationPreferencesGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.entities.notification.enums import NotificationCategory
from learnic.entities.notification_preferences.models import (
    NotificationPreferences,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateNotificationPreferencesCommand:
    """Full snapshot of the toggle matrix as posted by the settings UI.

    The UI sends every cell on each save — partial PATCH semantics
    would force the handler to reconcile against the stored row,
    and the matrix is small enough (channels × categories) that
    full replacement is the simpler contract.
    """

    actor_id: UserID
    push: dict[NotificationCategory, bool]
    email: dict[NotificationCategory, bool]


@final
class UpdateNotificationPreferencesCommandHandler:
    """Replace the caller's preferences with the supplied matrix.

    ``IN_APP`` is intentionally not part of the input — it is
    always on at the domain level. The HTTP schema mirrors that
    by omitting in-app from the request body so the wire format
    cannot misrepresent it.
    """

    def __init__(
        self,
        transaction: Transaction,
        gateway: NotificationPreferencesGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._gateway: Final = gateway

    async def run(
        self,
        data: UpdateNotificationPreferencesCommand,
    ) -> None:
        preferences = NotificationPreferences(
            user_id=data.actor_id,
            push=dict(data.push),
            email=dict(data.email),
        )
        await self._gateway.upsert(preferences)
        await self._transaction.commit()
