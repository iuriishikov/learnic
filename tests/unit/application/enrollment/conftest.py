import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.user.models import UserID


@pytest.fixture
def fake_transaction() -> AsyncMock:
    tx = AsyncMock()
    tx.commit = AsyncMock()
    tx.rollback = AsyncMock()
    return tx


@pytest.fixture
def fake_entity_saver() -> MagicMock:
    saver = MagicMock()
    saver.add_one = MagicMock()
    return saver


@pytest.fixture
def fake_enrollment_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    gw.with_product_and_student = AsyncMock(return_value=None)
    gw.with_cohort_and_student = AsyncMock(return_value=None)
    gw.for_cohort = AsyncMock(return_value=[])
    return gw


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_release_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.latest_for_product = AsyncMock()
    return gw


@pytest.fixture
def fake_cohort_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_authorizer() -> AsyncMock:
    az = AsyncMock()
    az.require = AsyncMock(return_value=None)
    return az


@pytest.fixture
def fake_user_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def student_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())
