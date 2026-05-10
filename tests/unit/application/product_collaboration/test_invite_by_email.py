from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product_collaboration._grant_spec import (
    GrantSpec,
)
from learnic.application.commands.product_collaboration.invite_by_email import (
    MAX_EMAIL_INVITES_PER_DAY,
    InviteCollaboratorByEmailCommand,
    InviteCollaboratorByEmailCommandHandler,
)
from learnic.application.common.errors import (
    EmailInviteRateLimitExceededError,
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
    fake_scheduler: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
) -> InviteCollaboratorByEmailCommandHandler:
    return InviteCollaboratorByEmailCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        hierarchy=fake_hierarchy,
        product_gateway=fake_product_gateway,
        user_gateway=fake_user_gateway,
        collab_gateway=fake_collab_gateway,
        collab_saver=fake_collab_saver,
        role_gateway=fake_role_gateway,
        lineage=fake_lineage_reader,
        scheduler=fake_scheduler,
        event_bus=fake_event_bus,
        notifications=fake_notifications,
        security=security_config,
    )


def _command(
    actor: UserID,
    product_id: ProductID,
    target_email: str,
    role_id: RoleID,
) -> InviteCollaboratorByEmailCommand:
    return InviteCollaboratorByEmailCommand(
        actor_id=actor,
        product_id=product_id,
        target_email=target_email,
        grants=[
            GrantSpec(
                role_id=role_id,
                scope_type=ScopeType.PRODUCT,
                scope_id=None,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_refuses_when_actor_hit_daily_email_invite_limit(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_scheduler: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_email.return_value = None
    fake_role_gateway.with_id.return_value = _custom_role(role_id, product)
    fake_collab_gateway.count_email_invites_by_actor_since.return_value = (
        MAX_EMAIL_INVITES_PER_DAY
    )

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
        fake_scheduler,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    with pytest.raises(EmailInviteRateLimitExceededError) as excinfo:
        await handler.run(
            _command(actor_id, product.oid, "fresh@example.com", role_id),
        )

    assert excinfo.value.actor_id == actor_id
    assert excinfo.value.limit == MAX_EMAIL_INVITES_PER_DAY
    assert excinfo.value.retry_after_seconds == 86400
    fake_collab_saver.save.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_scheduler.schedule_send_email.assert_not_called()


@pytest.mark.asyncio
async def test_allows_when_actor_below_daily_limit(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_scheduler: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_email.return_value = None
    fake_role_gateway.with_id.return_value = _custom_role(role_id, product)
    fake_collab_gateway.count_email_invites_by_actor_since.return_value = (
        MAX_EMAIL_INVITES_PER_DAY - 1
    )

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
        fake_scheduler,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    oid = await handler.run(
        _command(actor_id, product.oid, "fresh@example.com", role_id),
    )

    assert oid is not None
    fake_collab_saver.save.assert_called_once()
    fake_transaction.commit.assert_called_once()
    fake_scheduler.schedule_send_email.assert_called_once()
    fake_notifications.publish.assert_not_called()


@pytest.mark.asyncio
async def test_publishes_in_app_notification_for_registered_email(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_hierarchy: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_collab_saver: AsyncMock,
    fake_role_gateway: AsyncMock,
    fake_lineage_reader: AsyncMock,
    fake_scheduler: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    security_config,
    product: Product,
    actor_id: UserID,
    invitee_user: User,
    role_id: RoleID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_email.return_value = invitee_user
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
        fake_scheduler,
        fake_event_bus,
        fake_notifications,
        security_config,
    )
    oid = await handler.run(
        _command(actor_id, product.oid, invitee_user.email.value, role_id),
    )

    assert oid is not None
    fake_notifications.publish.assert_called_once()
    notification = fake_notifications.publish.call_args.args[0]
    assert notification.recipient_id == invitee_user.oid
    assert notification.actor_id == actor_id
