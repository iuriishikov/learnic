import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)
from learnic.infrastructure.configs import SecurityConfig


@pytest.fixture
def security_config() -> SecurityConfig:
    return SecurityConfig(
        jwt_secret="test-secret-at-least-32-bytes-long!",
        frontend_base_url="http://0.0.0.0:8000",
        cookie_secure=False,
    )


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_user_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    gateway.with_email = AsyncMock()
    return gateway


@pytest.fixture
def fake_refresh_store() -> AsyncMock:
    store = AsyncMock()
    store.revoke_all_for_user = AsyncMock(return_value=set())
    return store


@pytest.fixture
def fake_denylist() -> AsyncMock:
    dl = AsyncMock()
    dl.deny_family = AsyncMock()
    return dl


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    gateway.delete = AsyncMock()
    return gateway


@pytest.fixture
def fake_files_reader() -> AsyncMock:
    reader = AsyncMock()
    reader.file_ids_for_product = AsyncMock(return_value=[])
    return reader


@pytest.fixture
def fake_file_uploads() -> AsyncMock:
    uploads = AsyncMock()
    uploads.soft_delete_previous = AsyncMock()
    return uploads


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def regular_user() -> User:
    return User(
        oid=UserID(uuid.uuid4()),
        email=Email("user@example.com"),
        first_name=FirstName("Ivan"),
        last_name=LastName("Ivanov"),
        patronymic=None,
        password_hash=PasswordHash("hashed"),
        email_verified=True,
    )


@pytest.fixture
def fake_product() -> MagicMock:
    """Stand-in product entity — the delete handler only reads ``oid``."""
    product = MagicMock()
    product.oid = uuid.uuid4()
    return product
