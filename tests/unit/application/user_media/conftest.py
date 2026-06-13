import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
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
def fake_files_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock(return_value=None)
    return gateway


@pytest.fixture
def fake_file_uploads() -> AsyncMock:
    """Stub ``FileUploadService`` for handlers that mutate file state.

    ``upload_stream`` returns a fresh ``File`` so callers get a real
    ``oid`` to link via ``user.set_avatar(file.oid)``;
    ``soft_delete_previous`` is just an awaitable so we can assert it
    was (or wasn't) called.
    """

    def _build_file(upload: IncomingUpload, uploaded_by: UserID) -> File:
        return File(
            oid=FileID(uuid.uuid4()),
            storage_name=StorageName(str(uuid.uuid4())),
            bucket=StorageBucket("test-bucket"),
            content_type=ContentType(upload.content_type),
            size_bytes=FileSize(upload.size),
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

    svc = MagicMock()
    svc.upload_stream = AsyncMock(side_effect=_build_file)
    # Avatar / cover / icon flows go through the image-only variant; it
    # enforces the ``image/*`` content type before delegating to
    # ``upload_stream`` (that enforcement is unit-tested on the service
    # itself, so here it is a thin stub returning a real ``File``).
    svc.upload_image_stream = AsyncMock(side_effect=_build_file)
    svc.soft_delete_previous = AsyncMock()
    return svc


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
