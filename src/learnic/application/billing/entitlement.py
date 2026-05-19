"""Plan-aware policy service.

The application-layer entry point for everything billing decides:
which plan a user is on, how much storage they're using, and whether
a pending upload fits inside the plan's cap. Commands depend on this
service through its plain class — there's no Protocol indirection
because the service has no infrastructure dependencies of its own,
only protocols that already live in :mod:`learnic.application`.

**Quota ownership.** Storage is anchored on the *product author*,
not on the upload's actor. A collaborator uploading into the
author's course consumes the author's quota; the collaborator's own
plan governs only the products they themselves author. Every
quota-changing entry point therefore takes the quota owner's user
id, and every caller resolves that owner via ``product.author_id``.
"""

from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import StorageQuotaExceededError
from learnic.application.common.persistence.billing import (
    FileUsageReader,
    StorageQuotaLock,
    SubscriptionGateway,
)
from learnic.entities.billing.plan import Plan, default_plan, plan_for
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class StorageQuotaSnapshot:
    """Plan limit + current usage + remaining headroom for one owner.

    ``remaining_bytes`` is clamped at zero — over-quota state (e.g.
    after a plan downgrade) reports as "0 free" rather than a
    negative number the SPA would have to defend against.
    """

    plan: Plan
    used_bytes: int
    remaining_bytes: int


@final
class EntitlementService:
    """Resolve plans and enforce per-plan resource caps.

    All reads are independent (current_plan + storage_used) so callers
    that need both pay two round-trips; that's fine — both queries are
    cheap (indexed lookup + an aggregate over the file-blocks union).
    Optimise (cache, batch) only after a profile shows it matters.
    """

    def __init__(
        self,
        subscription_gateway: SubscriptionGateway,
        file_usage_reader: FileUsageReader,
        quota_lock: StorageQuotaLock,
    ) -> None:
        self._subscription_gateway: Final = subscription_gateway
        self._file_usage_reader: Final = file_usage_reader
        self._quota_lock: Final = quota_lock

    async def current_plan(self, user_id: UserID) -> Plan:
        """Return the plan the user is currently on.

        Falls back to the in-code DEFAULT_PLAN (FREE) when the user
        has no active subscription row. Raises
        :class:`UnknownPlanCodeError` if a stored plan_code has no
        matching entry in the registry — loud failure on drift.
        """
        subscription = await self._subscription_gateway.current_for_user(
            user_id,
        )
        if subscription is None:
            return default_plan()
        return plan_for(subscription.plan_code)

    async def storage_used(self, user_id: UserID) -> int:
        """Return aggregate bytes used across the user's own courses.

        Counts files referenced from courses where ``user_id`` is the
        author. Files the user uploaded into a collaborator's course
        are NOT counted here — they belong to that course's author.
        """
        return await self._file_usage_reader.bytes_used_by_course_author(
            user_id,
        )

    async def snapshot_for(
        self,
        quota_owner_id: UserID,
    ) -> StorageQuotaSnapshot:
        """Return plan + used + remaining for ``quota_owner_id``.

        Used by read-only endpoints (e.g. "how much can still be
        uploaded into this course"). No advisory lock is taken — the
        result is informational and may go stale between the read
        and any subsequent upload, which is exactly the contract
        :meth:`ensure_can_upload` enforces at write time.
        """
        plan = await self.current_plan(quota_owner_id)
        used = await self.storage_used(quota_owner_id)
        remaining = max(0, plan.limits.storage_bytes_max - used)
        return StorageQuotaSnapshot(
            plan=plan,
            used_bytes=used,
            remaining_bytes=remaining,
        )

    async def ensure_can_upload(
        self,
        quota_owner_id: UserID,
        attempted_bytes: int,
    ) -> None:
        """Raise if ``attempted_bytes`` would push the owner past their cap.

        Called by file-backed block commands BEFORE constructing the
        block. ``quota_owner_id`` is the product author whose quota
        will be charged for the upload — never the actor, since
        collaborators consume the author's plan, not their own.
        ``attempted_bytes`` is the total new bytes being added in
        this operation (the single file's size for file/video-file
        blocks; the sum of all item sizes for a photo-collage add).

        Concurrency: takes a per-owner transaction-scoped advisory
        lock BEFORE reading current usage. Concurrent uploads against
        the same owner serialize at this point and observe each
        other's committed bytes; cross-owner traffic is unaffected.
        The lock auto-releases on COMMIT or ROLLBACK of the calling
        handler's transaction.

        Raises:
            StorageQuotaExceededError: ``used + attempted`` exceeds the
                plan's ``storage_bytes_max``. HTTP 413.
        """
        await self._ensure_can_upload_delta(
            quota_owner_id,
            added_bytes=attempted_bytes,
            freed_bytes=0,
        )

    async def ensure_can_replace_upload(
        self,
        quota_owner_id: UserID,
        added_bytes: int,
        freed_bytes: int,
    ) -> None:
        """Quota check for replace-semantic block updates.

        ``added_bytes`` is the total size of the new uploads;
        ``freed_bytes`` is the total size of files the replace will
        unreference. The effective delta is
        ``max(0, added_bytes - freed_bytes)`` — a pure shrink (new
        <= freed) always passes the cap check even when the owner
        is currently at 100 % usage.

        Same per-owner advisory lock + author-scoped read as
        :meth:`ensure_can_upload`.

        **Trade-off the caller accepts.** ``freed_bytes`` is computed
        from the size of the *old* item files; if any of those files
        is also referenced from another block, removing it from this
        collage does NOT actually free space in the
        ``DISTINCT files.oid`` aggregate. Counting it as freed is a
        bounded false-allow — preferable to a false-reject on a
        legitimate shrink (the historical reason quota was skipped
        on this path entirely) and bounded by the size of the old
        block, so it cannot let an unbounded upload through.

        Raises:
            StorageQuotaExceededError: effective delta would push
                the owner past the plan cap. The error reports the
                effective delta as ``attempted_bytes``.
        """
        await self._ensure_can_upload_delta(
            quota_owner_id,
            added_bytes=added_bytes,
            freed_bytes=freed_bytes,
        )

    async def _ensure_can_upload_delta(
        self,
        quota_owner_id: UserID,
        *,
        added_bytes: int,
        freed_bytes: int,
    ) -> None:
        effective = max(0, added_bytes - freed_bytes)
        await self._quota_lock.acquire_for(quota_owner_id)
        if effective == 0:
            return
        plan = await self.current_plan(quota_owner_id)
        used = await self.storage_used(quota_owner_id)
        if used + effective > plan.limits.storage_bytes_max:
            raise StorageQuotaExceededError(
                plan_code=plan.code,
                used_bytes=used,
                attempted_bytes=effective,
                limit_bytes=plan.limits.storage_bytes_max,
            )
