from learnic.entities.common.errors import DomainError


class UnknownPlanCodeError(DomainError):
    """Raised when a stored plan code has no matching entry in PLANS.

    Indicates drift between the persisted ``subscriptions.plan_code``
    column and the in-code plan registry — most likely because a plan
    was renamed or removed in code without a backfill migration. Loud
    failure on read is intentional; silently falling back to FREE
    would hide the drift.
    """

    plan_code: str
