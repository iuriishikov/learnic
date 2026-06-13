import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.billing.revoke_subscription import (
    RevokeSubscriptionCommand,
    RevokeSubscriptionCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.billing.models import Subscription
from learnic.entities.billing.plan import BETA
from learnic.entities.user.models import User, UserID


def _active_grant(user_id: UserID) -> Subscription:
    """An indefinite, unrevoked grant — i.e. currently active."""
    return Subscription.create_subscription(
        user_id=user_id,
        plan_code=BETA,
        granted_by=UserID(uuid.uuid4()),
    )


async def test_revoke_stamps_single_active_grant_and_commits(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_subscription_gateway: AsyncMock,
    target_user: User,
) -> None:
    grant = _active_grant(target_user.oid)
    fake_user_gateway.with_id.return_value = target_user
    fake_subscription_gateway.active_for_user.return_value = [grant]

    handler = RevokeSubscriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        subscription_gateway=fake_subscription_gateway,
    )
    await handler.run(RevokeSubscriptionCommand(user_id=target_user.oid))

    assert grant.revoked_at is not None
    assert grant.is_active() is False
    fake_transaction.commit.assert_awaited_once()


async def test_revoke_drops_every_active_grant(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_subscription_gateway: AsyncMock,
    target_user: User,
) -> None:
    grants = [_active_grant(target_user.oid) for _ in range(3)]
    fake_user_gateway.with_id.return_value = target_user
    fake_subscription_gateway.active_for_user.return_value = grants

    handler = RevokeSubscriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        subscription_gateway=fake_subscription_gateway,
    )
    await handler.run(RevokeSubscriptionCommand(user_id=target_user.oid))

    assert all(g.revoked_at is not None for g in grants)
    fake_transaction.commit.assert_awaited_once()


async def test_revoke_user_already_free_is_a_no_op_success(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_subscription_gateway: AsyncMock,
    target_user: User,
) -> None:
    # No active grants => nothing to revoke, but the call still
    # succeeds (idempotent) and commits the empty unit of work.
    fake_user_gateway.with_id.return_value = target_user
    fake_subscription_gateway.active_for_user.return_value = []

    handler = RevokeSubscriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        subscription_gateway=fake_subscription_gateway,
    )
    await handler.run(RevokeSubscriptionCommand(user_id=target_user.oid))

    fake_transaction.commit.assert_awaited_once()


async def test_revoke_unknown_user_raises_and_does_not_commit(
    fake_transaction: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_subscription_gateway: AsyncMock,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = RevokeSubscriptionCommandHandler(
        transaction=fake_transaction,
        user_gateway=fake_user_gateway,
        subscription_gateway=fake_subscription_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            RevokeSubscriptionCommand(user_id=UserID(uuid.uuid4())),
        )

    fake_subscription_gateway.active_for_user.assert_not_awaited()
    fake_transaction.commit.assert_not_awaited()
