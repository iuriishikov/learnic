"""In-code plan registry — the source of truth for tariff limits.

Tariffs are defined in code rather than in a DB table. Trade-offs:
changing limits or adding a plan requires a deploy (we don't have an
admin UI to edit them); in exchange the limits get type-safe lookup,
single-source-of-truth semantics (no drift between code and DB), and
adding a tier is a one-line registry entry.

Subscriptions in the DB carry only a ``plan_code`` foreign-keyed (by
value, not by FK constraint) into this registry. The fail-fast in
:func:`plan_for` surfaces drift loudly.
"""

from dataclasses import dataclass
from typing import Final

from learnic.entities.billing.constants import (
    BETA_PLAN_STORAGE_BYTES,
    FREE_PLAN_STORAGE_BYTES,
)
from learnic.entities.billing.errors import UnknownPlanCodeError
from learnic.entities.billing.ids import PlanCode


@dataclass(frozen=True, slots=True)
class PlanLimits:
    """Per-plan resource caps.

    Only ``storage_bytes_max`` today — extend with future fields
    (e.g. ``max_courses``, ``max_students``) when the first concrete
    use case shows up. YAGNI defaults to "don't add a knob until
    something will turn it."
    """

    storage_bytes_max: int


@dataclass(frozen=True, slots=True)
class Plan:
    """One tariff entry — code + display name + caps."""

    code: PlanCode
    name: str
    limits: PlanLimits


FREE: Final[PlanCode] = PlanCode("FREE")
BETA: Final[PlanCode] = PlanCode("BETA")

PLANS: Final[dict[PlanCode, Plan]] = {
    FREE: Plan(
        code=FREE,
        name="Free",
        limits=PlanLimits(storage_bytes_max=FREE_PLAN_STORAGE_BYTES),
    ),
    BETA: Plan(
        code=BETA,
        name="Beta",
        limits=PlanLimits(storage_bytes_max=BETA_PLAN_STORAGE_BYTES),
    ),
}

# Every user without an active subscription falls back to this plan.
DEFAULT_PLAN_CODE: Final[PlanCode] = FREE


def plan_for(code: PlanCode) -> Plan:
    """Resolve a stored plan code into its in-code :class:`Plan`.

    Raises:
        UnknownPlanCodeError: ``code`` has no matching entry in
            :data:`PLANS` — almost certainly a code/DB drift bug.
    """
    plan = PLANS.get(code)
    if plan is None:
        raise UnknownPlanCodeError(plan_code=code)
    return plan


def default_plan() -> Plan:
    """Return the fallback plan used when a user has no subscription."""
    return PLANS[DEFAULT_PLAN_CODE]
