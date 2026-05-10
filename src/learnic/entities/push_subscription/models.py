import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.push_subscription.ids import PushSubscriptionID
from learnic.entities.user.models import UserID


@dataclass
class PushSubscription(BaseEntity[PushSubscriptionID]):
    """A single Web Push endpoint registered for a user-device pair.

    Browsers hand the SPA a :class:`PushSubscription` JSON object
    after the user grants notification permission. The SPA forwards
    ``endpoint``, ``p256dh`` and ``auth`` to the backend; we keep
    them so the worker can sign per-subscription deliveries with
    VAPID. ``user_agent`` is captured for the settings UI ("Chrome
    on macOS") — purely informational.

    The endpoint string is unique per subscription: re-subscribing
    the same browser produces a fresh endpoint, so duplicates are
    a sign of stale rows. The infrastructure adapter performs an
    upsert by ``endpoint`` to keep the latest keys in place.
    """

    user_id: UserID
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None
    created_at: datetime
    last_seen_at: datetime

    @classmethod
    def create(
        cls,
        *,
        user_id: UserID,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str | None,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=PushSubscriptionID(uuid.uuid4()),
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            user_agent=user_agent,
            created_at=moment,
            last_seen_at=moment,
        )

    def touch(self, *, now: datetime | None = None) -> None:
        self.last_seen_at = now or datetime.now(timezone.utc)
