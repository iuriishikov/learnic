"""Periodic reconcile of authors over their plan's storage cap.

Driven by an external scheduler (k8s CronJob / similar) through
:meth:`TaskScheduler.schedule_reconcile_storage_quotas`. One pass
covers every author with any deduplicated storage usage today:

1. **Detection.** For each author whose used bytes exceed their
   plan cap, upsert a :class:`StorageQuotaBreach` row (insert on
   first detection, refresh overage if the breach is already
   recorded — ``detected_at`` is preserved so the grace countdown
   does not reset).
2. **Notification.** If no notification was sent in the last
   ``OVER_QUOTA_NOTIFICATION_COOLDOWN_DAYS`` for this open breach,
   publish a ``storage_quota_warning`` card carrying the over-bytes
   and the absolute ``grace_until`` cutoff.
3. **Enforcement.** Once ``now - breach.detected_at >=
   OVER_QUOTA_GRACE_PERIOD_DAYS``, walk the author's files
   newest-first and soft-delete them until used bytes drop to the
   cap. Publish a ``storage_quota_enforced`` card with the count
   and freed bytes. Drop the breach record.
4. **Recovery.** Authors who freed up space on their own (or
   upgraded plans) have their breach record dropped without any
   notification — silence is fine, the in-app subscription view
   already reflects the new state.

Each author is processed in isolation: failures are logged and the
loop moves on so one bad row cannot stall the whole pass. The
notification publisher commits its own transaction internally, so
each author's mutations land atomically with the published card.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.billing import (
    AuthorActiveFilesReader,
    FileUsageReader,
    GlobalSchedulerLock,
    StorageQuotaBreachGateway,
)
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.billing.constants import (
    OVER_QUOTA_GRACE_PERIOD_DAYS,
    OVER_QUOTA_NOTIFICATION_COOLDOWN_DAYS,
)
from learnic.entities.billing.models import StorageQuotaBreach
from learnic.entities.billing.plan import Plan
from learnic.entities.notification.models import Notification
from learnic.entities.user.models import UserID

_logger = logging.getLogger(__name__)

# Cluster-wide key for the daily reconcile pass. Hardens the
# handler against accidentally-scaled scheduler deployments: a
# duplicate tick lands as a second TaskIQ task, the worker enters
# this handler, fails ``try_acquire`` immediately, and exits. The
# legitimate single replica scenario is unaffected.
_RECONCILE_LOCK_KEY: Final = "storage_quota_reconcile"


@dataclass(slots=True, frozen=True)
class ReconcileStorageQuotasCommand:
    """No arguments — the job scans the whole user base.

    Kept as a dataclass for shape-consistency with every other
    handler's command DTO so the dishka wiring and the eventual
    test harness do not need a special case.
    """


@dataclass(slots=True, frozen=True)
class ReconcileSummary:
    """Outcome of one reconcile pass.

    Surfaced to the caller (TaskIQ handler) primarily for
    structured logging — there is no business consumer.
    """

    scanned: int
    breaches_opened: int
    breaches_refreshed: int
    breaches_resolved: int
    enforcements: int
    warnings_sent: int


@final
class ReconcileStorageQuotasCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        entitlement: EntitlementService,
        file_usage: FileUsageReader,
        breaches: StorageQuotaBreachGateway,
        author_files: AuthorActiveFilesReader,
        file_uploads: FileUploadService,
        publisher: NotificationPublisher,
        scheduler_lock: GlobalSchedulerLock,
        quota_publisher: StorageQuotaUsagePublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._entitlement: Final = entitlement
        self._file_usage: Final = file_usage
        self._breaches: Final = breaches
        self._author_files: Final = author_files
        self._file_uploads: Final = file_uploads
        self._publisher: Final = publisher
        self._scheduler_lock: Final = scheduler_lock
        self._quota_publisher: Final = quota_publisher

    async def run(
        self,
        data: ReconcileStorageQuotasCommand,  # noqa: ARG002
    ) -> ReconcileSummary:
        if not await self._scheduler_lock.try_acquire(_RECONCILE_LOCK_KEY):
            _logger.info("storage_quota_reconcile.skipped_already_running")
            return _MutableSummary().frozen()
        try:
            return await self._run_locked()
        finally:
            await self._scheduler_lock.release(_RECONCILE_LOCK_KEY)

    async def _run_locked(self) -> ReconcileSummary:
        usage = await self._file_usage.usage_by_all_authors()
        open_breaches = {
            b.user_id: b for b in await self._breaches.all_open()
        }
        # Author may have zero usage now (deleted everything) but
        # still hold an open breach — process those too so the row
        # gets cleared.
        candidates = set(usage.keys()) | set(open_breaches.keys())

        summary = _MutableSummary()
        now = datetime.now(timezone.utc)
        for user_id in candidates:
            try:
                await self._process_user(
                    user_id=user_id,
                    used=usage.get(user_id, 0),
                    breach=open_breaches.get(user_id),
                    now=now,
                    summary=summary,
                )
            except Exception:  # noqa: BLE001 — per-user isolation.
                _logger.exception(
                    "storage_quota_reconcile.user_failed",
                    extra={"user_id": str(user_id)},
                )
                await self._transaction.rollback()
        return summary.frozen()

    async def _process_user(
        self,
        *,
        user_id: UserID,
        used: int,
        breach: StorageQuotaBreach | None,
        now: datetime,
        summary: "_MutableSummary",
    ) -> None:
        summary.scanned += 1
        plan = await self._entitlement.current_plan(user_id)
        cap = plan.limits.storage_bytes_max
        over_bytes = used - cap

        if over_bytes <= 0:
            if breach is not None:
                await self._breaches.delete(breach)
                await self._transaction.commit()
                summary.breaches_resolved += 1
            return

        if breach is None:
            breach = StorageQuotaBreach.create_breach(
                user_id=user_id,
                plan_code=plan.code,
                over_bytes=over_bytes,
            )
            self._entity_saver.add_one(breach)
            # Flush so the publisher's commit lands the new breach row
            # alongside the warning notification atomically.
            await self._transaction.flush()
            summary.breaches_opened += 1
        else:
            breach.refresh_overage(over_bytes)
            summary.breaches_refreshed += 1

        elapsed = now - breach.detected_at
        if elapsed >= timedelta(days=OVER_QUOTA_GRACE_PERIOD_DAYS):
            await self._enforce(
                user_id=user_id,
                used=used,
                plan=plan,
                breach=breach,
                summary=summary,
            )
            return

        if self._should_notify(breach, now):
            await self._send_warning(
                user_id=user_id,
                plan=plan,
                breach=breach,
                now=now,
            )
            summary.warnings_sent += 1
            return

        # Breach persists but cooldown is not yet over — just commit
        # the refresh and move on.
        await self._transaction.commit()

    def _should_notify(
        self,
        breach: StorageQuotaBreach,
        now: datetime,
    ) -> bool:
        if breach.last_notified_at is None:
            return True
        cooldown = timedelta(days=OVER_QUOTA_NOTIFICATION_COOLDOWN_DAYS)
        return now - breach.last_notified_at >= cooldown

    async def _send_warning(
        self,
        *,
        user_id: UserID,
        plan: Plan,
        breach: StorageQuotaBreach,
        now: datetime,
    ) -> None:
        grace_until = breach.detected_at + timedelta(
            days=OVER_QUOTA_GRACE_PERIOD_DAYS,
        )
        breach.record_notification(at=now)
        notification = Notification.for_storage_quota_warning(
            recipient_id=user_id,
            plan_code=plan.code,
            over_bytes=breach.over_bytes,
            plan_limit_bytes=plan.limits.storage_bytes_max,
            grace_until=grace_until,
            now=now,
        )
        await self._publisher.publish(notification)

    async def _enforce(
        self,
        *,
        user_id: UserID,
        used: int,
        plan: Plan,
        breach: StorageQuotaBreach,
        summary: "_MutableSummary",
    ) -> None:
        cap = plan.limits.storage_bytes_max
        to_free = used - cap
        candidates = await self._author_files.newest_first(user_id)
        freed = 0
        deleted_count = 0
        for ref in candidates:
            if freed >= to_free:
                break
            # soft_delete_previous spares files a published release
            # still pins (it shares the exact blob) — releases stay
            # immutable even under enforcement. Only credit the bytes
            # it actually evicted, and keep walking so a spared file
            # does not stall reclamation of the next candidate.
            if await self._file_uploads.soft_delete_previous(ref.file_id):
                freed += ref.size_bytes
                deleted_count += 1

        # Drop the breach: this enforcement pass should bring the
        # author back under cap. If somehow it didn't (race with
        # a concurrent upload), the next reconcile will reopen a
        # fresh breach with a new ``detected_at``.
        await self._breaches.delete(breach)
        notification = Notification.for_storage_quota_enforced(
            recipient_id=user_id,
            plan_code=plan.code,
            deleted_files_count=deleted_count,
            freed_bytes=freed,
        )
        await self._publisher.publish(notification)
        if deleted_count:
            await self._quota_publisher.usage_changed(user_id)
        summary.enforcements += 1


@dataclass(slots=True)
class _MutableSummary:
    """Internal counter bag — exposed as :class:`ReconcileSummary` on exit."""

    scanned: int = 0
    breaches_opened: int = 0
    breaches_refreshed: int = 0
    breaches_resolved: int = 0
    enforcements: int = 0
    warnings_sent: int = 0

    def frozen(self) -> ReconcileSummary:
        return ReconcileSummary(
            scanned=self.scanned,
            breaches_opened=self.breaches_opened,
            breaches_refreshed=self.breaches_refreshed,
            breaches_resolved=self.breaches_resolved,
            enforcements=self.enforcements,
            warnings_sent=self.warnings_sent,
        )
