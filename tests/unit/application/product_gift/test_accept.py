import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product_gift.accept import (
    AcceptGiftByTokenCommand,
    AcceptGiftByTokenCommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    NotResourceOwnerError,
)
from learnic.application.common.product_events import GiftAcceptedPayload
from learnic.entities.product.models import Product
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.product_gift.value_objects import InviteToken
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
)


def _build_handler(
    *,
    fake_transaction: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_service: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
) -> AcceptGiftByTokenCommandHandler:
    return AcceptGiftByTokenCommandHandler(
        transaction=fake_transaction,
        gift_gateway=fake_gift_gateway,
        user_gateway=fake_user_gateway,
        product_gateway=fake_product_gateway,
        enrollment_service=fake_enrollment_service,
        notifications=fake_notifications,
        event_bus=fake_event_bus,
    )


async def test_accept_creates_enrollment_and_notifies(
    fake_transaction: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_service: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    product: Product,
    recipient_id: UserID,
    recipient_user: User,
    pending_gift: ProductGift,
    gift_token: InviteToken,
) -> None:
    fake_gift_gateway.with_id.return_value = pending_gift
    fake_user_gateway.with_id.return_value = recipient_user
    fake_product_gateway.with_id.return_value = product
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_gift_gateway=fake_gift_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_product_gateway=fake_product_gateway,
        fake_enrollment_service=fake_enrollment_service,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
    )

    await handler.run(
        AcceptGiftByTokenCommand(
            actor_id=recipient_id,
            gift_id=pending_gift.oid,
            raw_token=gift_token.value,
        ),
    )

    assert pending_gift.status is GiftStatus.ACCEPTED
    enroll_kwargs = fake_enrollment_service.enroll.call_args.kwargs
    assert enroll_kwargs["student_id"] == recipient_id
    fake_notifications.publish.assert_awaited_once()
    fake_notifications.republish_for_gift.assert_awaited_once()
    # Collaborators watching the editor get a ``gift_accepted`` event.
    fake_event_bus.publish.assert_awaited_once()
    published = fake_event_bus.publish.call_args.args[0]
    assert isinstance(published.payload, GiftAcceptedPayload)
    assert published.payload.gift_id == str(pending_gift.oid)


async def test_accept_rejects_non_addressee(
    fake_transaction: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_service: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    product: Product,
    pending_gift: ProductGift,
    gift_token: InviteToken,
) -> None:
    stranger_id = UserID(uuid.uuid4())
    stranger = User(
        oid=stranger_id,
        email=Email("stranger@example.com"),
        first_name=FirstName("St"),
        last_name=LastName("Ranger"),
        patronymic=None,
        password_hash=PasswordHash("hash"),
        email_verified=True,
    )
    fake_gift_gateway.with_id.return_value = pending_gift
    fake_user_gateway.with_id.return_value = stranger
    fake_product_gateway.with_id.return_value = product
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_gift_gateway=fake_gift_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_product_gateway=fake_product_gateway,
        fake_enrollment_service=fake_enrollment_service,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
    )

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            AcceptGiftByTokenCommand(
                actor_id=stranger_id,
                gift_id=pending_gift.oid,
                raw_token=gift_token.value,
            ),
        )
    fake_enrollment_service.enroll.assert_not_called()


async def test_accept_already_enrolled_is_benign(
    fake_transaction: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_service: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    product: Product,
    recipient_id: UserID,
    recipient_user: User,
    pending_gift: ProductGift,
    gift_token: InviteToken,
) -> None:
    fake_gift_gateway.with_id.return_value = pending_gift
    fake_user_gateway.with_id.return_value = recipient_user
    fake_product_gateway.with_id.return_value = product
    fake_enrollment_service.enroll.side_effect = AlreadyEnrolledError(
        product.oid,
        recipient_id,
    )
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_gift_gateway=fake_gift_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_product_gateway=fake_product_gateway,
        fake_enrollment_service=fake_enrollment_service,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
    )

    await handler.run(
        AcceptGiftByTokenCommand(
            actor_id=recipient_id,
            gift_id=pending_gift.oid,
            raw_token=gift_token.value,
        ),
    )

    # Gift still accepted and committed despite the existing enrollment.
    assert pending_gift.status is GiftStatus.ACCEPTED
    fake_transaction.commit.assert_awaited_once()
    fake_notifications.publish.assert_awaited_once()
