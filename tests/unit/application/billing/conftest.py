"""Shared fixtures for billing-aggregate unit tests.

Every handler under test is constructed manually with ``AsyncMock``
dependencies (see CLAUDE.md — unit tests for application handlers
do not use dishka). Fixture names mirror the constructor parameter
names so wiring up a handler in a test reads naturally::

    handler = ReconcileStorageQuotasCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        ...
    )
"""

import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock

from learnic.application.billing.entitlement import EntitlementService
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    # ``EntitySaver.add_one`` is sync in the protocol; an AsyncMock
    # here would return a coroutine on each call and pytest would
    # complain about it never being awaited.
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_subscription_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.current_for_user = AsyncMock(return_value=None)
    gw.active_for_user = AsyncMock(return_value=[])
    return gw


@pytest.fixture
def fake_user_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    return gateway


@pytest.fixture
def target_user() -> User:
    """A plain user standing in for a subscription grant recipient."""
    return User(
        oid=UserID(uuid.uuid4()),
        email=Email("student@example.com"),
        first_name=FirstName("Anna"),
        last_name=LastName("Petrova"),
        patronymic=None,
        password_hash=PasswordHash("hashed"),
        email_verified=True,
    )


@pytest.fixture
def fake_file_usage_reader() -> AsyncMock:
    reader = AsyncMock()
    reader.bytes_used_by_note_author = AsyncMock(return_value=0)
    reader.usage_by_all_authors = AsyncMock(return_value={})
    return reader


@pytest.fixture
def fake_breach_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_user = AsyncMock(return_value=None)
    gw.all_open = AsyncMock(return_value=[])
    gw.delete = AsyncMock()
    return gw


@pytest.fixture
def fake_storage_quota_lock() -> AsyncMock:
    lock = AsyncMock()
    lock.acquire_for = AsyncMock()
    return lock


@pytest.fixture
def fake_global_scheduler_lock() -> AsyncMock:
    lock = AsyncMock()
    lock.try_acquire = AsyncMock(return_value=True)
    lock.release = AsyncMock()
    return lock


@pytest.fixture
def fake_author_files_reader() -> AsyncMock:
    reader = AsyncMock()
    reader.newest_first = AsyncMock(return_value=[])
    return reader


@pytest.fixture
def fake_file_uploads() -> AsyncMock:
    service = AsyncMock()
    service.soft_delete_previous = AsyncMock()
    return service


@pytest.fixture
def fake_notification_publisher() -> AsyncMock:
    publisher = AsyncMock()
    publisher.publish = AsyncMock()
    return publisher


@pytest.fixture
def fake_files_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    # Default to "no release pins this file" so the purge worker's
    # release guard lets the happy-path tests proceed; tests that
    # exercise the guard override this to ``True``.
    gw.is_referenced_by_release = AsyncMock(return_value=False)
    gw.delete = AsyncMock()
    return gw


@pytest.fixture
def fake_block_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.remove_file_from_collages = AsyncMock()
    return gw


@pytest.fixture
def fake_file_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.delete = AsyncMock()
    return storage


@pytest.fixture
def entitlement_service(
    fake_subscription_gateway: AsyncMock,
    fake_file_usage_reader: AsyncMock,
    fake_storage_quota_lock: AsyncMock,
) -> EntitlementService:
    """Real EntitlementService wired with mocked persistence.

    Used in :mod:`test_entitlement_service` (we exercise the
    actual quota arithmetic and lock-acquire ordering, not the
    DB calls). For reconcile tests where we want to control the
    plan returned without computing it, inject an ``AsyncMock``
    directly instead.
    """
    return EntitlementService(
        subscription_gateway=fake_subscription_gateway,
        file_usage_reader=fake_file_usage_reader,
        quota_lock=fake_storage_quota_lock,
    )
