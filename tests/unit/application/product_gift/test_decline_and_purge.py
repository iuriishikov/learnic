from unittest.mock import AsyncMock

from learnic.application.commands.product_gift.decline_in_app import (
    DeclineGiftCommand,
    DeclineGiftCommandHandler,
)
from learnic.application.commands.product_gift.purge_expired_invites import (
    PurgeExpiredGiftsCommand,
    PurgeExpiredGiftsCommandHandler,
)
from learnic.application.common.product_events import GiftDeclinedPayload
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import User, UserID


async def test_decline_flips_status_and_notifies_gifter(
    fake_transaction: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    recipient_id: UserID,
    recipient_user: User,
    pending_gift: ProductGift,
) -> None:
    fake_gift_gateway.with_id.return_value = pending_gift
    fake_user_gateway.with_id.return_value = recipient_user
    handler = DeclineGiftCommandHandler(
        transaction=fake_transaction,
        gift_gateway=fake_gift_gateway,
        user_gateway=fake_user_gateway,
        notifications=fake_notifications,
        event_bus=fake_event_bus,
    )

    await handler.run(
        DeclineGiftCommand(
            actor_id=recipient_id,
            gift_id=pending_gift.oid,
        ),
    )

    assert pending_gift.status is GiftStatus.DECLINED
    fake_transaction.commit.assert_awaited_once()
    fake_notifications.republish_for_gift.assert_awaited_once()
    fake_notifications.publish.assert_awaited_once()
    # Collaborators watching the editor get a ``gift_declined`` event.
    fake_event_bus.publish.assert_awaited_once()
    published = fake_event_bus.publish.call_args.args[0]
    assert isinstance(published.payload, GiftDeclinedPayload)
    assert published.payload.gift_id == str(pending_gift.oid)


async def test_purge_delegates_to_gateway(
    fake_transaction: AsyncMock,
    fake_gift_gateway: AsyncMock,
) -> None:
    fake_gift_gateway.delete_expired_pending_invites.return_value = 3
    handler = PurgeExpiredGiftsCommandHandler(
        transaction=fake_transaction,
        gift_gateway=fake_gift_gateway,
    )

    summary = await handler.run(PurgeExpiredGiftsCommand())

    assert summary.deleted == 3
    fake_gift_gateway.delete_expired_pending_invites.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()
