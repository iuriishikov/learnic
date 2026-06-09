"""Unit tests for ``StorageQuotaUsagePublisher``.

The publisher reads a fresh committed snapshot from
``EntitlementService.snapshot_for`` and pushes a full
``StorageQuotaUsageEvent`` onto the owner's channel. These tests
mock both collaborators and assert the projection (snapshot ->
event) and the publish call shape — no real Postgres, S3, or Redis.

All fixtures are kept inline on purpose; this file does not rely on
``tests/unit/application/billing/conftest.py``.
"""

import uuid
from unittest.mock import AsyncMock

from learnic.application.billing.entitlement import (
    EntitlementService,
    StorageQuotaSnapshot,
)
from learnic.application.common.storage_quota.event_bus import (
    StorageQuotaEventBus,
    StorageQuotaEventKind,
    StorageQuotaUsageEvent,
)
from learnic.application.common.storage_quota.publisher import (
    StorageQuotaUsagePublisher,
)
from learnic.entities.billing.plan import FREE, Plan, PlanLimits
from learnic.entities.user.models import UserID


_STORAGE_MAX = 2 * 1024 * 1024 * 1024
_USED = 500 * 1024 * 1024


def _snapshot() -> StorageQuotaSnapshot:
    plan = Plan(
        code=FREE,
        name="Free",
        limits=PlanLimits(storage_bytes_max=_STORAGE_MAX),
    )
    return StorageQuotaSnapshot(
        plan=plan,
        used_bytes=_USED,
        remaining_bytes=_STORAGE_MAX - _USED,
    )


async def test_usage_changed_publishes_snapshot_for_owner() -> None:
    owner_id = UserID(uuid.uuid4())
    snapshot = _snapshot()
    entitlement = AsyncMock(spec=EntitlementService)
    entitlement.snapshot_for = AsyncMock(return_value=snapshot)
    event_bus = AsyncMock(spec=StorageQuotaEventBus)
    event_bus.publish = AsyncMock()
    publisher = StorageQuotaUsagePublisher(
        entitlement=entitlement,
        event_bus=event_bus,
    )

    await publisher.usage_changed(owner_id)

    entitlement.snapshot_for.assert_awaited_once_with(owner_id)
    event_bus.publish.assert_awaited_once()

    published_owner = event_bus.publish.await_args.args[0]
    event = event_bus.publish.await_args.args[1]
    assert published_owner == owner_id
    assert isinstance(event, StorageQuotaUsageEvent)
    assert event.kind is StorageQuotaEventKind.USAGE_CHANGED
    assert event.plan_code == snapshot.plan.code
    assert event.storage_bytes_max == snapshot.plan.limits.storage_bytes_max
    assert event.storage_bytes_used == snapshot.used_bytes
    assert event.storage_bytes_remaining == snapshot.remaining_bytes
