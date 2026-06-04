import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.entities.note_module.models import NoteModule
from learnic.entities.note_module.value_objects import ModuleTitle
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
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
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_module_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    gw.for_product = AsyncMock(return_value=[])
    gw.delete = AsyncMock()
    gw.reorder = AsyncMock()
    return gw


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def other_user_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def note_product(author_id: UserID) -> Product:
    return Product.create_note(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )


@pytest.fixture
def note_module(note_product: Product) -> NoteModule:
    return NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("Intro"),
        position=0,
    )
