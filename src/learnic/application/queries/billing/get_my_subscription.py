from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.persistence.billing import (
    SubscriptionReader,
)
from learnic.entities.billing.ids import PlanCode
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMySubscriptionQuery:
    actor_id: UserID


@dataclass(slots=True, frozen=True)
class PlanLimitsView:
    storage_bytes_max: int


@dataclass(slots=True, frozen=True)
class PlanInfoView:
    code: PlanCode
    name: str
    limits: PlanLimitsView


@dataclass(slots=True, frozen=True)
class StorageUsageView:
    storage_bytes: int


@dataclass(slots=True, frozen=True)
class MySubscriptionView:
    """Caller-scoped projection for ``GET /users/me/subscription``.

    ``expires_at`` is ``None`` when the user is on the in-code default
    plan (no subscription row) OR when an active subscription was
    granted indefinitely.
    """

    plan: PlanInfoView
    used: StorageUsageView
    expires_at: datetime | None


@final
class GetMySubscriptionQueryHandler:
    """Compose plan + usage + expiry into one view for the caller.

    The query joins the in-code plan registry, the persisted current
    subscription (or absence thereof), and the storage-usage aggregate
    — three reads, all cheap.
    """

    def __init__(
        self,
        subscription_reader: SubscriptionReader,
        entitlement: EntitlementService,
    ) -> None:
        self._subscription_reader: Final = subscription_reader
        self._entitlement: Final = entitlement

    async def run(self, data: GetMySubscriptionQuery) -> MySubscriptionView:
        plan = await self._entitlement.current_plan(data.actor_id)
        used_bytes = await self._entitlement.storage_used(data.actor_id)
        subscription = await self._subscription_reader.current_for_user(
            data.actor_id,
        )
        expires_at = (
            subscription.expires_at if subscription is not None else None
        )
        return MySubscriptionView(
            plan=PlanInfoView(
                code=plan.code,
                name=plan.name,
                limits=PlanLimitsView(
                    storage_bytes_max=plan.limits.storage_bytes_max,
                ),
            ),
            used=StorageUsageView(storage_bytes=used_bytes),
            expires_at=expires_at,
        )
