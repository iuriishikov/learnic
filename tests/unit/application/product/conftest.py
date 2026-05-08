import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

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
def fake_file_storage() -> AsyncMock:
    storage = AsyncMock()
    storage.put = AsyncMock()
    return storage


@pytest.fixture
def fake_s3_config() -> MagicMock:
    config = MagicMock()
    config.bucket = "test-bucket"
    return config


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
