import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.role.delete import (
    DeleteCustomRoleCommand,
    DeleteCustomRoleCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    RoleInUseError,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.enums import RoleKind
from learnic.entities.role.ids import RoleID
from learnic.entities.role.models import Role
from learnic.entities.role.permissions import Permission
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleName,
    RolePosition,
)
from learnic.entities.user.models import UserID


def _custom_role(product_id: ProductID, creator: UserID) -> Role:
    now = datetime.now(timezone.utc)
    return Role(
        oid=RoleID(uuid.uuid4()),
        product_id=product_id,
        kind=RoleKind.CUSTOM,
        name=RoleName("Editor"),
        description=None,
        position=RolePosition(1010),
        created_by=creator,
        created_at=now,
        updated_at=now,
        permissions=PermissionSet.of(Permission.READ_PRODUCT),
    )


def _system_role() -> Role:
    now = datetime.now(timezone.utc)
    return Role(
        oid=RoleID(uuid.uuid4()),
        product_id=None,
        kind=RoleKind.SYSTEM,
        name=RoleName("Editor"),
        description=None,
        position=RolePosition(200),
        created_by=None,
        created_at=now,
        updated_at=now,
        permissions=PermissionSet.of(Permission.READ_PRODUCT),
    )


@pytest.mark.asyncio
async def test_deletes_when_not_in_use(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_role_gateway: AsyncMock,
    author_id: UserID,
    product_id: ProductID,
) -> None:
    role = _custom_role(product_id, author_id)
    fake_role_gateway.with_id.return_value = role
    fake_role_gateway.is_in_use.return_value = False

    handler = DeleteCustomRoleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        role_gateway=fake_role_gateway,
    )
    await handler.run(
        DeleteCustomRoleCommand(actor_id=author_id, role_id=role.oid),
    )
    fake_role_gateway.delete.assert_called_once_with(role)
    fake_transaction.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refuses_when_in_use(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_role_gateway: AsyncMock,
    author_id: UserID,
    product_id: ProductID,
) -> None:
    role = _custom_role(product_id, author_id)
    fake_role_gateway.with_id.return_value = role
    fake_role_gateway.is_in_use.return_value = True

    handler = DeleteCustomRoleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        role_gateway=fake_role_gateway,
    )
    with pytest.raises(RoleInUseError):
        await handler.run(
            DeleteCustomRoleCommand(
                actor_id=author_id,
                role_id=role.oid,
            ),
        )
    fake_role_gateway.delete.assert_not_called()
    fake_transaction.commit.assert_not_called()


@pytest.mark.asyncio
async def test_404_for_system_role(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_role_gateway: AsyncMock,
    author_id: UserID,
) -> None:
    fake_role_gateway.with_id.return_value = _system_role()

    handler = DeleteCustomRoleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        role_gateway=fake_role_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            DeleteCustomRoleCommand(
                actor_id=author_id,
                role_id=RoleID(uuid.uuid4()),
            ),
        )
    fake_authorizer.require.assert_not_called()
