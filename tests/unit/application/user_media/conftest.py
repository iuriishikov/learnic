import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.file.models import File, FileID
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)
from learnic.infrastructure.configs import S3Config


@pytest.fixture
def s3_config() -> S3Config:
    return S3Config(
        endpoint="http://localhost:9000",
        access_key="test",
        secret_key="test",
        bucket="learnic",
        region="us-east-1",
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
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_user_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    return gateway


@pytest.fixture
def fake_files_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock(return_value=None)
    return gateway


@pytest.fixture
def fake_file_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.put = AsyncMock()
    storage.delete = AsyncMock()
    storage.presigned_get_url = AsyncMock(return_value="http://signed/url")
    return storage


@pytest.fixture
def user() -> User:
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
def existing_file(user: User) -> File:
    return File(
        oid=FileID(uuid.uuid4()),
        storage_name=StorageName("old.jpg"),
        bucket=StorageBucket("learnic"),
        content_type=ContentType("image/jpeg"),
        size_bytes=FileSize(1024),
        uploaded_by=user.oid,
        uploaded_at=datetime.now(timezone.utc),
        deleted_at=None,
    )
