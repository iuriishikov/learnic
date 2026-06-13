from learnic.entities.common.errors import DomainError, FieldError


class UnknownPlanCodeError(DomainError):
    """Raised when a stored plan code has no matching entry in PLANS.

    Indicates drift between the persisted ``subscriptions.plan_code``
    column and the in-code plan registry — most likely because a plan
    was renamed or removed in code without a backfill migration. Loud
    failure on read is intentional; silently falling back to FREE
    would hide the drift.

    Also surfaced (as HTTP 422) when an admin grants a subscription
    with a ``plan_code`` that is not in the registry — a typo on the
    admin grant endpoint, not necessarily DB drift.
    """

    plan_code: str


class SubscriptionExpiryInPastError(FieldError):
    """Raised when a grant is minted with an expiry at or before now.

    A subscription whose ``expires_at`` is already in the past would
    be born inactive (see :meth:`Subscription.is_active`), so minting
    one is almost always an admin mistake. Only the *minting* path
    (:meth:`Subscription.create_subscription`) enforces this — loading
    a historical, already-expired grant from the DB is perfectly
    valid and must not raise.
    """

    field: str = "expires_at"
    reason: str = "must_be_in_future"
