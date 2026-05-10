import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.cohort.models import Cohort
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
def fake_entity_saver() -> MagicMock:
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    return gateway


@pytest.fixture
def fake_cohort_gateway() -> AsyncMock:
    gateway = AsyncMock()
    gateway.with_id = AsyncMock()
    return gateway


@pytest.fixture
def fake_authorizer() -> AsyncMock:
    authorizer = AsyncMock()
    authorizer.require = AsyncMock(return_value=None)
    return authorizer


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def host_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def stranger_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def webinar_product(author_id: UserID) -> Product:
    return Product.create_webinar(
        author_id=author_id,
        name=ProductTitle("Live SQL"),
        description=ProductDescription("<p>Live.</p>"),
        total_duration_in_hours=DurationHours(8),
        total_lessons=WebinarLessonsCount(4),
        default_duration_minutes=WebinarSessionDuration(90),
        allow_recording=True,
    )


@pytest.fixture
def course_product(author_id: UserID) -> Product:
    return Product.create_course(
        author_id=author_id,
        name=ProductTitle("Async Python"),
        description=ProductDescription("<p>Course.</p>"),
        total_duration_in_hours=DurationHours(20),
    )


@pytest.fixture
def cohort(webinar_product: Product, host_id: UserID) -> Cohort:
    return Cohort.create(
        webinar_id=webinar_product.oid,
        host_id=host_id,
        starts_on=date(2026, 9, 1),
    )
