import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.file.ids import FileID
from learnic.entities.file.models import File
from learnic.entities.file.value_objects import (
    ContentType,
    FileSize,
    StorageBucket,
    StorageName,
)
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import (
    DurationHours,
    ProductDescription,
    ProductTitle,
    WebinarLessonsCount,
    WebinarSessionDuration,
)
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    tx.flush = AsyncMock()
    return tx


@pytest.fixture
def fake_authorizer() -> AsyncMock:
    az = AsyncMock()
    az.require = AsyncMock()
    az.effective_permissions = AsyncMock(return_value=None)
    return az


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    gateway.delete = AsyncMock()
    return gateway


@pytest.fixture
def fake_product_reader() -> AsyncMock:
    reader = AsyncMock()
    reader.name_exists = AsyncMock(return_value=False)
    return reader


@pytest.fixture
def fake_html_sanitizer() -> MagicMock:
    sanitizer = MagicMock()
    sanitizer.sanitize = MagicMock(side_effect=lambda raw: raw)
    return sanitizer


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def fake_file_uploads() -> MagicMock:
    """Stub ``FileUploadService`` for product-creation tests.

    ``upload`` returns a fresh ``File`` entity so the handler can
    link its ``oid`` into the new product's ``cover_file_id``;
    ``soft_delete_previous`` is a no-op async stub.
    """

    def _build_file(data: bytes, content_type: str, uploaded_by: UserID) -> File:
        return File(
            oid=FileID(uuid.uuid4()),
            storage_name=StorageName(str(uuid.uuid4())),
            bucket=StorageBucket("test-bucket"),
            content_type=ContentType(content_type),
            size_bytes=FileSize(len(data)),
            uploaded_by=uploaded_by,
            uploaded_at=datetime.now(timezone.utc),
            deleted_at=None,
        )

    svc = MagicMock()
    svc.upload = AsyncMock(side_effect=_build_file)
    svc.soft_delete_previous = AsyncMock()
    return svc


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def other_user_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def course_product(author_id: UserID) -> Product:
    return Product.create_course(
        author_id=author_id,
        name=ProductTitle("Original course"),
        description=ProductDescription("<p>Original.</p>"),
        total_duration_in_hours=DurationHours(20),
    )


@pytest.fixture
def webinar_product(author_id: UserID) -> Product:
    return Product.create_webinar(
        author_id=author_id,
        name=ProductTitle("Original webinar"),
        description=ProductDescription("<p>Live.</p>"),
        total_duration_in_hours=DurationHours(8),
        total_lessons=WebinarLessonsCount(4),
        default_duration_minutes=WebinarSessionDuration(90),
        allow_recording=True,
    )
