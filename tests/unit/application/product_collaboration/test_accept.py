import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product_collaboration.accept import (
    AcceptCollaborationInviteCommand,
    AcceptCollaborationInviteCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InviteEmailMismatchError,
    NotResourceOwnerError,
)
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.product_collaboration.value_objects import InviteToken
from learnic.entities.role.permissions import ScopeType
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import Email


@pytest.mark.asyncio
async def test_accept_by_user_invite(
    fake_transaction: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    existing_collab: ProductCollaboration,
    invitee_user: User,
) -> None:
    fake_collab_gateway.with_id.return_value = existing_collab
    fake_user_gateway.with_id.return_value = invitee_user

    handler = AcceptCollaborationInviteCommandHandler(
        transaction=fake_transaction,
        collab_gateway=fake_collab_gateway,
        user_gateway=fake_user_gateway,
        event_bus=fake_event_bus,
        notifications=fake_notifications,
    )
    await handler.run(
        AcceptCollaborationInviteCommand(
            actor_id=invitee_user.oid,
            collaboration_id=existing_collab.oid,
            raw_token="plain-token-value",
        ),
    )
    assert existing_collab.status is CollaborationStatus.ACTIVE
    fake_transaction.commit.assert_called_once()
    fake_notifications.publish.assert_called_once()


@pytest.mark.asyncio
async def test_accept_rejects_wrong_user(
    fake_transaction: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    existing_collab: ProductCollaboration,
    invitee_user: User,
) -> None:
    fake_collab_gateway.with_id.return_value = existing_collab
    # actor != collaborator_id
    other = User(
        oid=UserID(uuid.uuid4()),
        email=Email("other@example.com"),
        first_name=invitee_user.first_name,
        last_name=invitee_user.last_name,
        patronymic=None,
        password_hash=invitee_user.password_hash,
        email_verified=True,
    )
    fake_user_gateway.with_id.return_value = other

    handler = AcceptCollaborationInviteCommandHandler(
        transaction=fake_transaction,
        collab_gateway=fake_collab_gateway,
        user_gateway=fake_user_gateway,
        event_bus=fake_event_bus,
        notifications=fake_notifications,
    )
    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            AcceptCollaborationInviteCommand(
                actor_id=other.oid,
                collaboration_id=existing_collab.oid,
                raw_token="plain-token-value",
            ),
        )
    fake_transaction.commit.assert_not_called()


@pytest.mark.asyncio
async def test_accept_email_invite_requires_email_match(
    fake_transaction: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
    product_id: object,
    actor_id: UserID,
) -> None:
    token = InviteToken("plain-token-value")
    collab = ProductCollaboration.invite_by_email(
        product_id=product_id,  # type: ignore[arg-type]
        invited_email=Email("invited@example.com"),
        invited_by=actor_id,
        grants=[
            CollaborationGrant.create(
                role_id=uuid.uuid4(),  # type: ignore[arg-type]
                scope_type=ScopeType.PRODUCT,
                scope_id=None,
            ),
        ],
        token=token,
    )
    fake_collab_gateway.with_id.return_value = collab
    other_email_user = User(
        oid=UserID(uuid.uuid4()),
        email=Email("someone-else@example.com"),
        first_name=actor_id_first_name(),
        last_name=actor_id_last_name(),
        patronymic=None,
        password_hash=password_hash(),
        email_verified=True,
    )
    fake_user_gateway.with_id.return_value = other_email_user

    handler = AcceptCollaborationInviteCommandHandler(
        transaction=fake_transaction,
        collab_gateway=fake_collab_gateway,
        user_gateway=fake_user_gateway,
        event_bus=fake_event_bus,
        notifications=fake_notifications,
    )
    with pytest.raises(InviteEmailMismatchError):
        await handler.run(
            AcceptCollaborationInviteCommand(
                actor_id=other_email_user.oid,
                collaboration_id=collab.oid,
                raw_token=token.value,
            ),
        )
    fake_transaction.commit.assert_not_called()


@pytest.mark.asyncio
async def test_404_when_collaboration_missing(
    fake_transaction: AsyncMock,
    fake_collab_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    fake_notifications: AsyncMock,
) -> None:
    fake_collab_gateway.with_id.return_value = None

    handler = AcceptCollaborationInviteCommandHandler(
        transaction=fake_transaction,
        collab_gateway=fake_collab_gateway,
        user_gateway=fake_user_gateway,
        event_bus=fake_event_bus,
        notifications=fake_notifications,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            AcceptCollaborationInviteCommand(
                actor_id=UserID(uuid.uuid4()),
                collaboration_id=ProductCollaborationID(uuid.uuid4()),
                raw_token="x" * 16,
            ),
        )


# Local helpers used to keep the email-mismatch test compact without
# importing User VO factory functions on every line.


def actor_id_first_name() -> object:
    from learnic.entities.user.value_objects import FirstName

    return FirstName("First")


def actor_id_last_name() -> object:
    from learnic.entities.user.value_objects import LastName

    return LastName("Last")


def password_hash() -> object:
    from learnic.entities.user.value_objects import PasswordHash

    return PasswordHash("hash")
