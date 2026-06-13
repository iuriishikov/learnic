import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.billing.errors import SubscriptionExpiryInPastError
from learnic.entities.billing.ids import (
    PlanCode,
    StorageQuotaBreachID,
    SubscriptionID,
)
from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.user.models import UserID


@dataclass
class Subscription(BaseEntity[SubscriptionID]):
    """A grant of a paid (or BETA) tier to a user.

    Active iff ``revoked_at`` is null AND (``expires_at`` is null OR
    ``expires_at > now()``). Multiple subscription rows per user are
    allowed — history of grants is preserved, the "current" one is
    derived at read time. New grants are issued as fresh INSERTs (not
    UPDATEs of an existing row) so audit trail stays intact.

    Absence of any active row means the user is on the default plan
    (FREE) — see :func:`learnic.entities.billing.plan.default_plan`.
    """

    user_id: UserID
    plan_code: PlanCode
    granted_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    granted_by: UserID | None = None

    def revoke(self, at: datetime | None = None) -> None:
        """Stamp ``revoked_at`` so subsequent reads ignore this row."""
        self.revoked_at = at or datetime.now(timezone.utc)

    def is_active(self, *, at: datetime | None = None) -> bool:
        """Return whether the grant is currently in force."""
        now = at or datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= now:
            return False
        return True

    @classmethod
    def create_subscription(
        cls,
        user_id: UserID,
        plan_code: PlanCode,
        expires_at: datetime | None = None,
        granted_by: UserID | None = None,
    ) -> Self:
        """Mint a new grant — used by admin / manual SQL paths.

        Until the payment integration ships, BETA grants are issued
        manually via direct SQL inserts; this factory exists so any
        future programmatic path (admin endpoint, CLI) uses the same
        construction.

        Args:
            user_id: The user receiving the grant.
            plan_code: Which in-code plan to grant.
            expires_at: When the grant lapses; ``None`` grants it
                indefinitely. Must be timezone-aware and strictly in
                the future when provided.
            granted_by: The admin who issued the grant, for audit.

        Raises:
            SubscriptionExpiryInPastError: ``expires_at`` is at or
                before the current instant, which would mint an
                already-inactive grant.
        """
        now = datetime.now(timezone.utc)
        if expires_at is not None and expires_at <= now:
            raise SubscriptionExpiryInPastError()
        return cls(
            oid=SubscriptionID(uuid.uuid4()),
            user_id=user_id,
            plan_code=plan_code,
            granted_at=now,
            expires_at=expires_at,
            granted_by=granted_by,
        )


@dataclass
class StorageQuotaBreach(BaseEntity[StorageQuotaBreachID]):
    """Outstanding over-quota state for one user.

    A row exists for the duration of a breach: created on first
    detection by the reconciliation job, refreshed on each subsequent
    scan while the breach persists, and deleted when the user either
    frees up space or upgrades back into compliance. ``user_id`` is
    UNIQUE — at most one open breach per user at a time.

    ``last_notified_at`` is ``None`` until the first notification
    fires (within the same scan that creates the row); subsequent
    notifications respect ``OVER_QUOTA_NOTIFICATION_COOLDOWN_DAYS``
    so the daily job does not spam inboxes. ``plan_code`` captures
    the plan at detection so notification copy stays consistent even
    if the user upgrades-then-downgrades during the breach.
    """

    user_id: UserID
    plan_code: PlanCode
    detected_at: datetime
    over_bytes: int
    last_notified_at: datetime | None = None

    def record_notification(self, at: datetime | None = None) -> None:
        self.last_notified_at = at or datetime.now(timezone.utc)

    def refresh_overage(self, over_bytes: int) -> None:
        """Update the recorded overage; ``detected_at`` is preserved.

        Grace counts from first detection, not from the latest scan
        — otherwise a user oscillating just above the cap would
        reset their countdown every day.
        """
        self.over_bytes = over_bytes

    @classmethod
    def create_breach(
        cls,
        user_id: UserID,
        plan_code: PlanCode,
        over_bytes: int,
    ) -> Self:
        return cls(
            oid=StorageQuotaBreachID(uuid.uuid4()),
            user_id=user_id,
            plan_code=plan_code,
            detected_at=datetime.now(timezone.utc),
            over_bytes=over_bytes,
            last_notified_at=None,
        )
