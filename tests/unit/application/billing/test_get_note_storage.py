"""Unit tests for ``GetNoteStorageQueryHandler``.

The handler resolves the note's author, gates the actor behind
``EDIT_LESSONS``, then projects a fresh entitlement snapshot plus this
note's own byte usage into a ``NoteStorageView``. These tests mock all
four collaborators (authorizer, product gateway, entitlement service,
file-usage reader) and assert the projection and the call shapes — no
real Postgres, S3, or Redis.

All fixtures are kept inline on purpose; this file does not rely on
``tests/unit/application/billing/conftest.py``.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from learnic.application.billing.entitlement import (
    EntitlementService,
    StorageQuotaSnapshot,
)
from learnic.application.common.auth.authorizer import Authorizer
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
)
from learnic.application.common.persistence.billing import FileUsageReader
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.queries.billing.get_note_storage import (
    GetNoteStorageQuery,
    GetNoteStorageQueryHandler,
)
from learnic.entities.billing.plan import FREE, Plan, PlanLimits
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID

_STORAGE_MAX = 2 * 1024 * 1024 * 1024
_USED = 500 * 1024 * 1024
_NOTE_USED = 120 * 1024 * 1024


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


def _handler(
    *,
    authorizer: AsyncMock,
    product_gateway: AsyncMock,
    entitlement: AsyncMock,
    file_usage: AsyncMock,
) -> GetNoteStorageQueryHandler:
    return GetNoteStorageQueryHandler(
        authorizer=authorizer,
        product_gateway=product_gateway,
        entitlement=entitlement,
        file_usage=file_usage,
    )


async def test_run_projects_snapshot_and_note_usage_on_happy_path() -> None:
    actor_id = UserID(uuid.uuid4())
    author_id = UserID(uuid.uuid4())
    note_id = ProductID(uuid.uuid4())
    snapshot = _snapshot()

    authorizer = AsyncMock(spec=Authorizer)
    authorizer.require = AsyncMock(return_value=None)
    product_gateway = AsyncMock(spec=ProductGateway)
    product_gateway.with_id = AsyncMock(
        return_value=SimpleNamespace(author_id=author_id),
    )
    entitlement = AsyncMock(spec=EntitlementService)
    entitlement.snapshot_for = AsyncMock(return_value=snapshot)
    file_usage = AsyncMock(spec=FileUsageReader)
    file_usage.bytes_used_by_product = AsyncMock(return_value=_NOTE_USED)

    handler = _handler(
        authorizer=authorizer,
        product_gateway=product_gateway,
        entitlement=entitlement,
        file_usage=file_usage,
    )

    view = await handler.run(
        GetNoteStorageQuery(actor_id=actor_id, note_id=note_id),
    )

    assert view.plan_code == snapshot.plan.code
    assert view.storage_bytes_max == snapshot.plan.limits.storage_bytes_max
    assert view.storage_bytes_used == snapshot.used_bytes
    assert view.storage_bytes_remaining == snapshot.remaining_bytes
    assert view.note_storage_bytes_used == _NOTE_USED

    # Quota is anchored on the author, not the actor.
    entitlement.snapshot_for.assert_awaited_once_with(author_id)
    assert author_id != actor_id
    file_usage.bytes_used_by_product.assert_awaited_once_with(note_id)


async def test_run_raises_when_product_missing() -> None:
    actor_id = UserID(uuid.uuid4())
    note_id = ProductID(uuid.uuid4())

    authorizer = AsyncMock(spec=Authorizer)
    authorizer.require = AsyncMock(return_value=None)
    product_gateway = AsyncMock(spec=ProductGateway)
    product_gateway.with_id = AsyncMock(return_value=None)
    entitlement = AsyncMock(spec=EntitlementService)
    entitlement.snapshot_for = AsyncMock()
    file_usage = AsyncMock(spec=FileUsageReader)
    file_usage.bytes_used_by_product = AsyncMock()

    handler = _handler(
        authorizer=authorizer,
        product_gateway=product_gateway,
        entitlement=entitlement,
        file_usage=file_usage,
    )

    with pytest.raises(EntityNotFoundError) as exc_info:
        await handler.run(
            GetNoteStorageQuery(actor_id=actor_id, note_id=note_id),
        )

    assert exc_info.value.entity_id == note_id
    entitlement.snapshot_for.assert_not_awaited()
    file_usage.bytes_used_by_product.assert_not_awaited()


async def test_run_propagates_when_authorizer_denies() -> None:
    actor_id = UserID(uuid.uuid4())
    author_id = UserID(uuid.uuid4())
    note_id = ProductID(uuid.uuid4())

    authorizer = AsyncMock(spec=Authorizer)
    authorizer.require = AsyncMock(
        side_effect=InsufficientPermissionsError(
            user_id=actor_id,
            product_id=note_id,
            permission="EDIT_LESSONS",
        ),
    )
    product_gateway = AsyncMock(spec=ProductGateway)
    product_gateway.with_id = AsyncMock(
        return_value=SimpleNamespace(author_id=author_id),
    )
    entitlement = AsyncMock(spec=EntitlementService)
    entitlement.snapshot_for = AsyncMock()
    file_usage = AsyncMock(spec=FileUsageReader)
    file_usage.bytes_used_by_product = AsyncMock()

    handler = _handler(
        authorizer=authorizer,
        product_gateway=product_gateway,
        entitlement=entitlement,
        file_usage=file_usage,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            GetNoteStorageQuery(actor_id=actor_id, note_id=note_id),
        )

    entitlement.snapshot_for.assert_not_awaited()
    file_usage.bytes_used_by_product.assert_not_awaited()
