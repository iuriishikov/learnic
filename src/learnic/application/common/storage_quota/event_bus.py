"""Per-owner storage-quota push channel.

Carries live "how full is my storage" numbers to the SPA so the
quota meter updates the moment an upload, replace, delete, or
reconcile eviction lands. Every event is a FULL snapshot of the
owner's pool (never a delta) — the client just replaces what it
shows, so a lost or out-of-order message self-heals on the next
event.

The channel is keyed by the **quota owner** (= note author; see
:mod:`learnic.application.billing.entitlement` for the ownership
rule). The WS endpoint subscribes the authenticated user to their
own key only.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from learnic.application.billing.entitlement import StorageQuotaSnapshot
from learnic.entities.billing.ids import PlanCode
from learnic.entities.user.models import UserID


class StorageQuotaEventKind(StrEnum):
    """Discriminator for the per-owner storage-quota channel.

    ``SNAPSHOT`` is route-generated: sent once right after the WS
    handshake (and again on every reconnect) so the client never
    needs a REST bootstrap. ``USAGE_CHANGED`` is producer-generated:
    published after a quota-changing command commits. Both carry
    the identical payload — the split exists only so the client
    can tell "initial state" from "something just happened".
    """

    SNAPSHOT = "snapshot"
    USAGE_CHANGED = "usage_changed"


@dataclass(slots=True, frozen=True)
class StorageQuotaUsageEvent:
    """Full quota snapshot for one owner at one point in time.

    Field names mirror ``NoteStorageRemainingSchema`` so the SPA
    reuses one wire shape for the REST read and the WS push.
    ``occurred_at`` lets the client drop a stale event that lost a
    race against a fresher one (publish order across concurrent
    commits is not guaranteed).
    """

    plan_code: PlanCode
    storage_bytes_max: int
    storage_bytes_used: int
    storage_bytes_remaining: int
    occurred_at: datetime
    kind: StorageQuotaEventKind = StorageQuotaEventKind.USAGE_CHANGED


def usage_event_from_snapshot(
    snapshot: StorageQuotaSnapshot,
    *,
    occurred_at: datetime,
    kind: StorageQuotaEventKind = StorageQuotaEventKind.USAGE_CHANGED,
) -> StorageQuotaUsageEvent:
    """Project an entitlement snapshot into a channel event."""
    return StorageQuotaUsageEvent(
        plan_code=snapshot.plan.code,
        storage_bytes_max=snapshot.plan.limits.storage_bytes_max,
        storage_bytes_used=snapshot.used_bytes,
        storage_bytes_remaining=snapshot.remaining_bytes,
        occurred_at=occurred_at,
        kind=kind,
    )


class StorageQuotaEventBus(Protocol):
    """Per-owner pub/sub channel for storage-quota snapshots.

    Mirrors :class:`NotificationEventBus` — Redis pub/sub keyed by
    ``quota_owner_id`` so a user opens exactly one socket to
    ``WS /users/me/storage`` and watches it across processes. The
    publisher is called by command handlers right after commit
    (via :class:`StorageQuotaUsagePublisher`); the subscriber
    lives in the WS endpoint.
    """

    async def publish(
        self,
        quota_owner_id: UserID,
        event: StorageQuotaUsageEvent,
    ) -> None: ...

    def subscribe(
        self,
        quota_owner_id: UserID,
    ) -> AsyncIterator[StorageQuotaUsageEvent]: ...
