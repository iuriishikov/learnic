from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.billing.ids import PlanCode, SubscriptionID
from learnic.entities.billing.models import Subscription
from learnic.entities.billing.plan import Plan, plan_for
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GrantSubscriptionCommand:
    """Admin grants a tariff to a user free of charge.

    ``actor_id`` is the granting administrator (stored as
    ``granted_by`` for audit). ``expires_at`` is timezone-aware; a
    ``None`` value grants the plan indefinitely.
    """

    actor_id: UserID
    user_id: UserID
    plan_code: PlanCode
    expires_at: datetime | None


@dataclass(slots=True, frozen=True)
class GrantedSubscription:
    """Result of a successful grant — the persisted row joined with
    the in-code plan it points at, so the route can render a full
    "tariff card" without re-resolving the registry.
    """

    oid: SubscriptionID
    user_id: UserID
    plan: Plan
    granted_at: datetime
    expires_at: datetime | None
    granted_by: UserID | None


@final
class GrantSubscriptionCommandHandler:
    """Issue a free subscription grant on behalf of an administrator.

    This is the programmatic counterpart to the manual SQL inserts
    used to seed BETA access before the payment integration lands
    (see :meth:`Subscription.create_subscription`). Each call appends
    a fresh grant row rather than mutating an existing one, preserving
    the audit trail — the user's "current" plan is the most recent
    active grant, so re-granting with a new expiry effectively
    extends or replaces access without losing history.

    Authorization (the caller must be a platform admin) is enforced
    at the HTTP boundary by ``AdminAuthenticator``; this handler only
    validates the target and the requested plan.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway

    async def run(
        self,
        data: GrantSubscriptionCommand,
    ) -> GrantedSubscription:
        # Resolve (and thereby validate) the requested plan against
        # the in-code registry first — a bad code is a cheap reject
        # before touching the DB.
        plan = plan_for(data.plan_code)
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        subscription = Subscription.create_subscription(
            user_id=data.user_id,
            plan_code=plan.code,
            expires_at=data.expires_at,
            granted_by=data.actor_id,
        )
        self._entity_saver.add_one(subscription)
        await self._transaction.commit()
        return GrantedSubscription(
            oid=subscription.oid,
            user_id=subscription.user_id,
            plan=plan,
            granted_at=subscription.granted_at,
            expires_at=subscription.expires_at,
            granted_by=subscription.granted_by,
        )
