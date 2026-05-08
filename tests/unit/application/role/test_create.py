import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.role.create import (
    CreateCustomRoleCommand,
    CreateCustomRoleCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    RoleNameAlreadyTakenError,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


def _command(
    actor: UserID,
    product_id: ProductID,
) -> CreateCustomRoleCommand:
    return CreateCustomRoleCommand(
        actor_id=actor,
        product_id=product_id,
        name="Lead Editor",
        permissions=frozenset({Permission.READ_PRODUCT}),
        description=None,
    )


@pytest.mark.asyncio
async def test_creates_role_when_authorized(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_role_reader: AsyncMock,
    fake_role_saver: AsyncMock,
    product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = product

    handler = CreateCustomRoleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        role_gateway=fake_role_gateway,
        role_reader=fake_role_reader,
        role_saver=fake_role_saver,
    )
    role_id = await handler.run(_command(author_id, product.oid))

    assert role_id is not None
    fake_authorizer.require.assert_called_once()
    fake_role_saver.save.assert_called_once()
    fake_transaction.commit.assert_called_once()


@pytest.mark.asyncio
async def test_404_when_product_missing(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_role_reader: AsyncMock,
    fake_role_saver: AsyncMock,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = None

    handler = CreateCustomRoleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        role_gateway=fake_role_gateway,
        role_reader=fake_role_reader,
        role_saver=fake_role_saver,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(_command(author_id, ProductID(uuid.uuid4())))
    fake_authorizer.require.assert_not_called()


@pytest.mark.asyncio
async def test_conflict_when_name_already_taken(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_role_reader: AsyncMock,
    fake_role_saver: AsyncMock,
    product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_role_gateway.with_name_for_product.return_value = object()

    handler = CreateCustomRoleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        role_gateway=fake_role_gateway,
        role_reader=fake_role_reader,
        role_saver=fake_role_saver,
    )
    with pytest.raises(RoleNameAlreadyTakenError):
        await handler.run(_command(author_id, product.oid))
    fake_role_saver.save.assert_not_called()
    fake_transaction.commit.assert_not_called()
