from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.push.gateway import PushSubscriptionGateway
from learnic.entities.push_subscription.models import PushSubscription
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListMyPushSubscriptionsQuery:
    actor_id: UserID


@final
class ListMyPushSubscriptionsQueryHandler:
    """Return the caller's registered Web Push subscriptions.

    Drives the "Devices" list in the settings UI — typically one
    row per browser-device combination. Lightweight: no joins,
    one Postgres roundtrip; we surface ``user_agent`` and
    ``last_seen_at`` so the UI can label rows ("Chrome on macOS,
    last used 2 days ago").
    """

    def __init__(self, gateway: PushSubscriptionGateway) -> None:
        self._gateway: Final = gateway

    async def run(
        self,
        data: ListMyPushSubscriptionsQuery,
    ) -> Sequence[PushSubscription]:
        return await self._gateway.list_for_user(data.actor_id)
