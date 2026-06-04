import uuid
from unittest.mock import AsyncMock

import pytest

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
    """Permissive authorizer — actor effectively has every permission.

    Tests that need a denial set ``effective_permissions.return_value``
    to ``None`` or to a narrower :class:`PermissionSet`.
    """
    from learnic.entities.role.permissions import Permission as _Perm
    from learnic.entities.role.value_objects import (
        PermissionSet as _PermSet,
    )

    az = AsyncMock()
    az.require = AsyncMock()
    az.effective_permissions = AsyncMock(
        return_value=_PermSet(frozenset(_Perm)),
    )
    return az


@pytest.fixture
def fake_product_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock()
    return gw


@pytest.fixture
def fake_role_gateway() -> AsyncMock:
    gw = AsyncMock()
    gw.with_id = AsyncMock(return_value=None)
    gw.with_name_for_product = AsyncMock(return_value=None)
    gw.is_in_use = AsyncMock(return_value=False)
    gw.delete = AsyncMock()
    return gw


@pytest.fixture
def fake_role_saver() -> AsyncMock:
    saver = AsyncMock()
    saver.save = AsyncMock()
    saver.replace_permissions = AsyncMock()
    return saver


@pytest.fixture
def fake_role_reader() -> AsyncMock:
    reader = AsyncMock()
    reader.with_id = AsyncMock(return_value=None)
    reader.for_product = AsyncMock(return_value=[])
    reader.max_position_in_product = AsyncMock(return_value=400)
    reader.min_position_for_user = AsyncMock(return_value=None)
    reader.count_for_product = AsyncMock(return_value=0)
    return reader


@pytest.fixture
def fake_event_bus() -> AsyncMock:
    bus = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
def author_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def product(author_id: UserID) -> Product:
    return Product.create_note(
        author_id=author_id,
        name=ProductTitle("Demo"),
    )


@pytest.fixture
def product_id(product: Product) -> ProductID:
    return product.oid
