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
    return gateway


@pytest.fixture
def fake_html_sanitizer() -> MagicMock:
    sanitizer = MagicMock()
    # echo input by default so tests see what the handler forwarded
    sanitizer.sanitize = AsyncMock(side_effect=lambda raw: raw)
    return sanitizer


@pytest.fixture
def user() -> User:
    return User(
        oid=UserID(uuid.uuid4()),
        email=Email("user@example.com"),
        first_name=FirstName("Old"),
        last_name=LastName("Name"),
        patronymic=None,
        password_hash=PasswordHash("hashed"),
        email_verified=True,
    )
