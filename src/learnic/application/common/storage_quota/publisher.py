"""Post-commit publisher for storage-quota usage events.

One injectable dependency instead of two: quota-changing command
handlers call :meth:`StorageQuotaUsagePublisher.usage_changed`
right after ``transaction.commit()`` and this service does the
rest — reads a fresh committed snapshot and pushes it to the
owner's channel. Reading AFTER commit is the point: the snapshot
reflects the mutation the handler just landed, and the publish
can never advertise rolled-back state (same rule as every other
event bus in this codebase).
"""

from datetime import datetime, timezone
from typing import Final, final

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.common.storage_quota.event_bus import (
    StorageQuotaEventBus,
    usage_event_from_snapshot,
)
from learnic.entities.user.models import UserID


@final
class StorageQuotaUsagePublisher:
    """Snapshot the owner's quota pool and broadcast it.

    No advisory lock is taken — the value is informational (the
    upload-time check re-validates under the per-owner lock), and
    every event is a full snapshot, so a racing publish degrades
    into a briefly-stale meter that the next event corrects.
    """

    def __init__(
        self,
        entitlement: EntitlementService,
        event_bus: StorageQuotaEventBus,
    ) -> None:
        self._entitlement: Final = entitlement
        self._event_bus: Final = event_bus

    async def usage_changed(self, quota_owner_id: UserID) -> None:
        """Publish a fresh ``usage_changed`` snapshot for the owner.

        Call strictly AFTER the mutating transaction commits so
        subscribers only ever observe committed usage.

        Args:
            quota_owner_id: The user whose pool changed — always
                the note author, never the acting collaborator.
        """
        snapshot = await self._entitlement.snapshot_for(quota_owner_id)
        await self._event_bus.publish(
            quota_owner_id,
            usage_event_from_snapshot(
                snapshot,
                occurred_at=datetime.now(timezone.utc),
            ),
        )
