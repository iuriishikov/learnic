"""Unit tests for ``ReconcileStorageQuotasCommandHandler`` state-machine.

The handler has one entry point but four real branches per user
(plus the global lock guard). Each test isolates one transition
on mocked dependencies — no real Postgres, S3, or TaskIQ broker.

Branches covered:

* No usage at all → scanned 0, no mutation.
* Under cap, no breach → no-op.
* Under cap, breach exists → silent resolve (delete breach, no notification).
* Over cap, no breach → create breach + send warning.
* Over cap, breach within grace, cooldown elapsed → refresh + remind.
* Over cap, breach within grace, cooldown active → refresh, suppress.
* Over cap, breach grace elapsed → enforce + drop breach + notify.

Plus a couple of cross-cutting properties:

* Global scheduler lock failure short-circuits the whole pass.
* ``detected_at`` is preserved across refresh (no countdown reset).
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from learnic.application.billing.entitlement import EntitlementService
from learnic.application.commands.billing.reconcile_storage_quotas import (
    ReconcileStorageQuotasCommand,
    ReconcileStorageQuotasCommandHandler,
)
from learnic.application.common.persistence.billing import AuthorFileRef
from learnic.entities.billing.ids import PlanCode, StorageQuotaBreachID
from learnic.entities.billing.models import StorageQuotaBreach
from learnic.entities.billing.plan import (
    BETA,
    FREE,
    Plan,
    PlanLimits,
)
from learnic.entities.file.ids import FileID
from learnic.entities.notification.enums import NotificationKind
from learnic.entities.user.models import UserID


_FREE_PLAN = Plan(
    code=FREE,
    name="Free",
    limits=PlanLimits(storage_bytes_max=2 * 1024 * 1024 * 1024),
)
_BETA_PLAN = Plan(
    code=BETA,
    name="Beta",
    limits=PlanLimits(storage_bytes_max=50 * 1024 * 1024 * 1024),
)


def _build_handler(
    *,
    transaction: AsyncMock,
    entity_saver: MagicMock,
    entitlement: EntitlementService | AsyncMock,
    file_usage: AsyncMock,
    breaches: AsyncMock,
    author_files: AsyncMock,
    file_uploads: AsyncMock,
    publisher: AsyncMock,
    scheduler_lock: AsyncMock,
    quota_publisher: AsyncMock | None = None,
) -> ReconcileStorageQuotasCommandHandler:
    return ReconcileStorageQuotasCommandHandler(
        transaction=transaction,
        entity_saver=entity_saver,
        entitlement=entitlement,  # type: ignore[arg-type]
        file_usage=file_usage,
        breaches=breaches,
        author_files=author_files,
        file_uploads=file_uploads,
        publisher=publisher,
        scheduler_lock=scheduler_lock,
        quota_publisher=quota_publisher or AsyncMock(),
    )


def _make_breach(
    *,
    user_id: UserID,
    detected_at: datetime,
    over_bytes: int = 1024,
    plan_code: PlanCode = FREE,
) -> StorageQuotaBreach:
    return StorageQuotaBreach(
        oid=StorageQuotaBreachID(uuid.uuid4()),
        user_id=user_id,
        plan_code=plan_code,
        detected_at=detected_at,
        over_bytes=over_bytes,
        last_notified_at=None,
    )


def _entitlement_returning(plan: Plan) -> AsyncMock:
    """Lightweight mock of ``EntitlementService`` that returns ``plan``.

    Used when a test does not care about the real plan-resolution
    logic and just wants to control the cap.
    """
    service = AsyncMock(spec=EntitlementService)
    service.current_plan = AsyncMock(return_value=plan)
    return service


async def test_skips_when_global_lock_already_taken(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    fake_global_scheduler_lock.try_acquire.return_value = False
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.scanned == 0
    fake_file_usage_reader.usage_by_all_authors.assert_not_called()
    fake_breach_gateway.all_open.assert_not_called()
    fake_global_scheduler_lock.release.assert_not_called()


async def test_no_usage_no_breaches_is_no_op(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.scanned == 0
    assert summary.breaches_opened == 0
    assert summary.enforcements == 0
    fake_notification_publisher.publish.assert_not_called()
    fake_global_scheduler_lock.release.assert_called_once()


async def test_under_cap_existing_breach_silent_resolve(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    breach = _make_breach(
        user_id=user_id,
        detected_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    fake_file_usage_reader.usage_by_all_authors.return_value = {user_id: 100}
    fake_breach_gateway.all_open.return_value = [breach]
    fake_quota_publisher = AsyncMock()
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
        quota_publisher=fake_quota_publisher,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.breaches_resolved == 1
    fake_breach_gateway.delete.assert_called_once_with(breach)
    fake_notification_publisher.publish.assert_not_called()
    # Breach-resolved path frees nothing → no quota snapshot.
    fake_quota_publisher.usage_changed.assert_not_awaited()


async def test_over_cap_no_breach_creates_and_warns(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    fake_file_usage_reader.usage_by_all_authors.return_value = {
        user_id: _FREE_PLAN.limits.storage_bytes_max + 500 * 1024 * 1024,
    }
    fake_quota_publisher = AsyncMock()
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
        quota_publisher=fake_quota_publisher,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.breaches_opened == 1
    assert summary.warnings_sent == 1
    fake_entity_saver.add_one.assert_called_once()
    saved_breach = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved_breach, StorageQuotaBreach)
    assert saved_breach.user_id == user_id
    assert saved_breach.over_bytes == 500 * 1024 * 1024

    fake_notification_publisher.publish.assert_called_once()
    notification = fake_notification_publisher.publish.call_args.args[0]
    assert notification.kind is NotificationKind.STORAGE_QUOTA_WARNING
    # Warning-only path deletes nothing → no quota snapshot.
    fake_quota_publisher.usage_changed.assert_not_awaited()


async def test_over_cap_breach_within_cooldown_does_not_renotify(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    now = datetime.now(timezone.utc)
    breach = _make_breach(
        user_id=user_id,
        detected_at=now - timedelta(days=1),
        over_bytes=100,
    )
    breach.record_notification(at=now - timedelta(hours=12))
    fake_file_usage_reader.usage_by_all_authors.return_value = {
        user_id: _FREE_PLAN.limits.storage_bytes_max + 200,
    }
    fake_breach_gateway.all_open.return_value = [breach]
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.breaches_refreshed == 1
    assert summary.warnings_sent == 0
    fake_notification_publisher.publish.assert_not_called()
    # over_bytes refreshed in-place; detected_at preserved.
    assert breach.over_bytes == 200


async def test_over_cap_breach_cooldown_elapsed_sends_reminder(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    now = datetime.now(timezone.utc)
    breach = _make_breach(
        user_id=user_id,
        detected_at=now - timedelta(days=5),
        over_bytes=100,
    )
    breach.record_notification(at=now - timedelta(days=4))
    fake_file_usage_reader.usage_by_all_authors.return_value = {
        user_id: _FREE_PLAN.limits.storage_bytes_max + 100,
    }
    fake_breach_gateway.all_open.return_value = [breach]
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.breaches_refreshed == 1
    assert summary.warnings_sent == 1
    fake_notification_publisher.publish.assert_called_once()


async def test_grace_elapsed_enforces_lifo(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    user_id = UserID(uuid.uuid4())
    cap = _FREE_PLAN.limits.storage_bytes_max
    used = cap + 700 * 1024 * 1024
    over = used - cap  # 700 MB
    breach = _make_breach(
        user_id=user_id,
        detected_at=datetime.now(timezone.utc) - timedelta(days=20),
        over_bytes=over,
    )
    f1 = AuthorFileRef(
        file_id=FileID(uuid.uuid4()),
        size_bytes=500 * 1024 * 1024,
    )
    f2 = AuthorFileRef(
        file_id=FileID(uuid.uuid4()),
        size_bytes=300 * 1024 * 1024,
    )
    f3 = AuthorFileRef(
        file_id=FileID(uuid.uuid4()),
        size_bytes=400 * 1024 * 1024,
    )
    fake_file_usage_reader.usage_by_all_authors.return_value = {user_id: used}
    fake_breach_gateway.all_open.return_value = [breach]
    fake_author_files_reader.newest_first.return_value = [f1, f2, f3]
    fake_quota_publisher = AsyncMock()
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
        quota_publisher=fake_quota_publisher,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.enforcements == 1
    # 500 MB + 300 MB ≥ 700 MB → loop stops at f2. f3 must NOT be
    # soft-deleted.
    assert fake_file_uploads.soft_delete_previous.await_count == 2
    deleted_ids = [
        call.args[0]
        for call in fake_file_uploads.soft_delete_previous.await_args_list
    ]
    assert deleted_ids == [f1.file_id, f2.file_id]
    fake_breach_gateway.delete.assert_called_once_with(breach)
    notification = fake_notification_publisher.publish.call_args.args[0]
    assert notification.kind is NotificationKind.STORAGE_QUOTA_ENFORCED
    # Files were swept → fresh quota snapshot published once for the
    # breached author (who IS user_id in the reconcile flow).
    fake_quota_publisher.usage_changed.assert_awaited_once_with(user_id)


async def test_enforce_spares_release_pinned_files(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    # Enforcement must not strip media out of a published release.
    # f1 is pinned by a release, so soft_delete_previous spares it
    # (returns False); the job keeps walking and credits only the
    # bytes of files it actually evicted (f2 + f3).
    user_id = UserID(uuid.uuid4())
    cap = _FREE_PLAN.limits.storage_bytes_max
    used = cap + 700 * 1024 * 1024
    over = used - cap  # 700 MB
    breach = _make_breach(
        user_id=user_id,
        detected_at=datetime.now(timezone.utc) - timedelta(days=20),
        over_bytes=over,
    )
    f1 = AuthorFileRef(
        file_id=FileID(uuid.uuid4()),
        size_bytes=500 * 1024 * 1024,
    )
    f2 = AuthorFileRef(
        file_id=FileID(uuid.uuid4()),
        size_bytes=400 * 1024 * 1024,
    )
    f3 = AuthorFileRef(
        file_id=FileID(uuid.uuid4()),
        size_bytes=300 * 1024 * 1024,
    )

    def _spare_f1(file_id: FileID) -> bool:
        return file_id != f1.file_id

    fake_file_uploads.soft_delete_previous.side_effect = _spare_f1
    fake_file_usage_reader.usage_by_all_authors.return_value = {user_id: used}
    fake_breach_gateway.all_open.return_value = [breach]
    fake_author_files_reader.newest_first.return_value = [f1, f2, f3]
    fake_quota_publisher = AsyncMock()
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
        quota_publisher=fake_quota_publisher,
    )

    summary = await handler.run(ReconcileStorageQuotasCommand())

    assert summary.enforcements == 1
    # All three were attempted; f1 spared, f2 + f3 evicted (700 MB).
    assert fake_file_uploads.soft_delete_previous.await_count == 3
    notification = fake_notification_publisher.publish.call_args.args[0]
    assert notification.details.deleted_files_count == 2
    assert notification.details.freed_bytes == 700 * 1024 * 1024


async def test_detected_at_preserved_on_refresh(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    # Grace counts from first detection — refresh must NOT bump
    # ``detected_at``, otherwise a user oscillating around the cap
    # could indefinitely delay enforcement.
    user_id = UserID(uuid.uuid4())
    original_detected_at = datetime.now(timezone.utc) - timedelta(days=10)
    breach = _make_breach(
        user_id=user_id,
        detected_at=original_detected_at,
        over_bytes=100,
    )
    fake_file_usage_reader.usage_by_all_authors.return_value = {
        user_id: _FREE_PLAN.limits.storage_bytes_max + 999,
    }
    fake_breach_gateway.all_open.return_value = [breach]
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_FREE_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
    )

    await handler.run(ReconcileStorageQuotasCommand())

    assert breach.detected_at == original_detected_at
    assert breach.over_bytes == 999


async def test_releases_lock_even_on_exception(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_file_usage_reader: AsyncMock,
    fake_breach_gateway: AsyncMock,
    fake_author_files_reader: AsyncMock,
    fake_file_uploads: AsyncMock,
    fake_notification_publisher: AsyncMock,
    fake_global_scheduler_lock: AsyncMock,
) -> None:
    # If anything inside the loop blows up beyond the per-user
    # isolation (e.g. ``usage_by_all_authors`` itself raises), the
    # finally MUST still release the global lock — otherwise the
    # next scheduled tick stays starved.
    fake_file_usage_reader.usage_by_all_authors.side_effect = RuntimeError(
        "db blew up",
    )
    handler = _build_handler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        entitlement=_entitlement_returning(_BETA_PLAN),
        file_usage=fake_file_usage_reader,
        breaches=fake_breach_gateway,
        author_files=fake_author_files_reader,
        file_uploads=fake_file_uploads,
        publisher=fake_notification_publisher,
        scheduler_lock=fake_global_scheduler_lock,
    )

    raised: Exception | None = None
    try:
        await handler.run(ReconcileStorageQuotasCommand())
    except RuntimeError as exc:  # noqa: BLE001
        raised = exc

    assert raised is not None
    fake_global_scheduler_lock.release.assert_called_once()
