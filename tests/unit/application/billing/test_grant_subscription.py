import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.billing.grant_subscription import (
    GrantSubscriptionCommand,
    GrantSubscriptionCommandHandler,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.entities.billing.errors import (
    SubscriptionExpiryInPastError,
    UnknownPlanCodeError,
)
from learnic.entities.billing.ids import PlanCode
from learnic.entities.billing.models import Subscription
from learnic.entities.billing.plan import BETA
from learnic.entities.user.models import User, UserID


def _command(
    *,
    actor_id: UserID,
    user_id: UserID,
    plan_code: PlanCode = BETA,
    expires_at: datetime | None = None,
) -> GrantSubscriptionCommand:
    return GrantSubscriptionCommand(
        actor_id=actor_id,
        user_id=user_id,
        plan_code=plan_code,
        expires_at=expires_at,
    )


async def test_grant_inserts_subscription_and_commits(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    target_user: User,
) -> None:
    fake_user_gateway.with_id.return_value = target_user
    admin_id = UserID(uuid.uuid4())

    handler = GrantSubscriptionCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
    )
    result = await handler.run(
        _command(actor_id=admin_id, user_id=target_user.oid),
    )

    # Persisted exactly one fresh Subscription, then committed.
    fake_entity_saver.add_one.assert_called_once()
    (saved,) = fake_entity_saver.add_one.call_args.args
    assert isinstance(saved, Subscription)
    assert saved.user_id == target_user.oid
    assert saved.plan_code == BETA
    assert saved.granted_by == admin_id
    assert saved.revoked_at is None
    fake_transaction.commit.assert_awaited_once()

    # Result joins the persisted row with the resolved in-code plan.
    assert result.plan.code == BETA
    assert result.plan.name == "Beta"
    assert result.user_id == target_user.oid
    assert result.granted_by == admin_id
    assert result.expires_at is None


async def test_grant_with_future_expiry_is_stored(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    target_user: User,
) -> None:
    fake_user_gateway.with_id.return_value = target_user
    expires = datetime.now(timezone.utc) + timedelta(days=30)

    handler = GrantSubscriptionCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
    )
    result = await handler.run(
        _command(
            actor_id=UserID(uuid.uuid4()),
            user_id=target_user.oid,
            expires_at=expires,
        ),
    )

    assert result.expires_at == expires
    fake_transaction.commit.assert_awaited_once()


async def test_grant_unknown_user_raises_and_does_not_commit(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
) -> None:
    fake_user_gateway.with_id.return_value = None

    handler = GrantSubscriptionCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
    )
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            _command(
                actor_id=UserID(uuid.uuid4()),
                user_id=UserID(uuid.uuid4()),
            ),
        )

    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_awaited()


async def test_grant_unknown_plan_raises_before_touching_db(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    target_user: User,
) -> None:
    # An unknown plan code is rejected by plan_for() before the user
    # lookup or any persistence, so the gateway is never even queried.
    fake_user_gateway.with_id.return_value = target_user

    handler = GrantSubscriptionCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
    )
    with pytest.raises(UnknownPlanCodeError):
        await handler.run(
            _command(
                actor_id=UserID(uuid.uuid4()),
                user_id=target_user.oid,
                plan_code=PlanCode("DEFINITELY_NOT_A_PLAN"),
            ),
        )

    fake_user_gateway.with_id.assert_not_awaited()
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_awaited()


async def test_grant_past_expiry_raises_and_does_not_commit(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_user_gateway: AsyncMock,
    target_user: User,
) -> None:
    fake_user_gateway.with_id.return_value = target_user
    past = datetime.now(timezone.utc) - timedelta(days=1)

    handler = GrantSubscriptionCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        user_gateway=fake_user_gateway,
    )
    with pytest.raises(SubscriptionExpiryInPastError):
        await handler.run(
            _command(
                actor_id=UserID(uuid.uuid4()),
                user_id=target_user.oid,
                expires_at=past,
            ),
        )

    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_awaited()
