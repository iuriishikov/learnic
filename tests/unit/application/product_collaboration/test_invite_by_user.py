import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product_collaboration._grant_spec import (
    GrantSpec,
)
from learnic.application.commands.product_collaboration.invite_by_user import (
    InviteCollaboratorByUserCommand,
    InviteCollaboratorByUserCommandHandler,
)
from learnic.application.common.errors import (
    CannotInviteOwnerError,
    CollaborationAlreadyExistsError,
    EntityNotFoundError,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.role.ids import RoleID
from learnic.entities.role.models import Role
from learnic.entities.role.permissions import Permission, ScopeType
from learnic.entities.role.value_objects import (
    PermissionSet,
    RoleName,
    RolePosition,
)
from learnic.entities.user.models import User, UserID


def _custom_role(role_id: RoleID, product: Product) -> Role:
    now = datetime.now(timezone.utc)
    return Role(
        oid=role_id,
        product_id=product.oid,
        name=RoleName("Editor"),
        description=None,
        position=RolePosition(1010),
        created_by=None,
        created_at=now,
        updated_at=now,
        permissions=PermissionSet.of(Permission.READ_PRODUCT),
    )


def _build_handler(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_notifier: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
) -> InviteCollaboratorByUserCommandHandler:
    return InviteCollaboratorByUserCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        hierarchy=fake_hierarchy,
        product_gateway=fake_product_gateway,
        user_gateway=fake_user_gateway,
        collab_gateway=fake_collab_gateway,
        collab_saver=fake_collab_saver,
        role_gateway=fake_role_gateway,
        lineage=fake_lineage_reader,
        notifier=fake_notifier,
        event_bus=fake_event_bus,
        notifications=fake_notifications,
        security=security_config,
    )


def _command(
    actor: UserID,
    product_id: ProductID,
    invitee: UserID,
    role_id: RoleID,
) -> InviteCollaboratorByUserCommand:
    return InviteCollaboratorByUserCommand(
        actor_id=actor,
        product_id=product_id,
        target_user_id=invitee,
        grants=[
            GrantSpec(
                role_id=role_id,
                scope_type=ScopeType.PRODUCT,
                scope_id=None,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_invites_and_schedules_email(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_notifier: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    invitee_id: UserID,
    invitee_user: User,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_id.return_value = invitee_user
    fake_role_gateway.with_id.return_value = _custom_role(role_id, product)

    handler = _build_handler(
        fake_transaction,
        fake_authorizer,
        fake_hierarchy,
        fake_product_gateway,
        fake_user_gateway,
        fake_collab_gateway,
        fake_collab_saver,
        fake_role_gateway,
        fake_lineage_reader,
        fake_notifier,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    oid = await handler.run(
        _command(actor_id, product.oid, invitee_id, role_id),
    )

    assert oid is not None
    fake_collab_saver.save.assert_called_once()
    fake_transaction.commit.assert_called_once()
    fake_notifier.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_refuses_to_invite_owner(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_notifier: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product

    handler = _build_handler(
        fake_transaction,
        fake_authorizer,
        fake_hierarchy,
        fake_product_gateway,
        fake_user_gateway,
        fake_collab_gateway,
        fake_collab_saver,
        fake_role_gateway,
        fake_lineage_reader,
        fake_notifier,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    with pytest.raises(CannotInviteOwnerError):
        await handler.run(
            _command(actor_id, product.oid, product.author_id, role_id),
        )
    fake_collab_saver.save.assert_not_called()


@pytest.mark.asyncio
async def test_refuses_when_user_missing(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_notifier: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    invitee_id: UserID,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_id.return_value = None

    handler = _build_handler(
        fake_transaction,
        fake_authorizer,
        fake_hierarchy,
        fake_product_gateway,
        fake_user_gateway,
        fake_collab_gateway,
        fake_collab_saver,
        fake_role_gateway,
        fake_lineage_reader,
        fake_notifier,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            _command(actor_id, product.oid, invitee_id, role_id),
        )


@pytest.mark.asyncio
async def test_refuses_when_collaboration_exists(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_notifier: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    invitee_id: UserID,
    invitee_user: User,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_id.return_value = invitee_user
    fake_collab_gateway.active_for_product_and_user.return_value = object()

    handler = _build_handler(
        fake_transaction,
        fake_authorizer,
        fake_hierarchy,
        fake_product_gateway,
        fake_user_gateway,
        fake_collab_gateway,
        fake_collab_saver,
        fake_role_gateway,
        fake_lineage_reader,
        fake_notifier,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    with pytest.raises(CollaborationAlreadyExistsError):
        await handler.run(
            _command(actor_id, product.oid, invitee_id, role_id),
        )


@pytest.mark.asyncio
async def test_refuses_when_role_missing(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_notifier: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    invitee_id: UserID,
    invitee_user: User,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_id.return_value = invitee_user
    fake_role_gateway.with_id.return_value = None

    handler = _build_handler(
        fake_transaction,
        fake_authorizer,
        fake_hierarchy,
        fake_product_gateway,
        fake_user_gateway,
        fake_collab_gateway,
        fake_collab_saver,
        fake_role_gateway,
        fake_lineage_reader,
        fake_notifier,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    bogus_role = RoleID(uuid.uuid4())
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            _command(actor_id, product.oid, invitee_id, bogus_role),
        )
