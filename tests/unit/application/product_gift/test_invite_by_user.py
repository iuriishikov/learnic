from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product_gift.invite_by_user import (
    InviteGiftByUserCommand,
    InviteGiftByUserCommandHandler,
)
from learnic.application.common.errors import (
    CannotGiftToOwnerError,
    GiftAlreadyExistsError,
    ProductNotGiftableError,
)
from learnic.application.common.product_events import GiftIssuedPayload
from learnic.entities.notification.enums import NotificationChannel
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import User, UserID


def _build_handler(
    *,
    fake_transaction: AsyncMock,
    fake_entity_saver: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_notifier: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    security_config: object,
) -> InviteGiftByUserCommandHandler:
    return InviteGiftByUserCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        user_gateway=fake_user_gateway,
        gift_gateway=fake_gift_gateway,
        notifier=fake_notifier,
        notifications=fake_notifications,
        event_bus=fake_event_bus,
        security=security_config,  # type: ignore[arg-type]
    )


async def test_invite_by_user_happy_path(
    fake_transaction: AsyncMock,
    fake_entity_saver: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_notifier: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    security_config: object,
    product: Product,
    product_id: ProductID,
    actor_id: UserID,
    recipient_id: UserID,
    recipient_user: User,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_id.return_value = recipient_user
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_entity_saver=fake_entity_saver,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_gift_gateway=fake_gift_gateway,
        fake_notifier=fake_notifier,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
        security_config=security_config,
    )

    oid = await handler.run(
        InviteGiftByUserCommand(
            actor_id=actor_id,
            product_id=product_id,
            recipient_id=recipient_id,
        ),
    )

    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, ProductGift)
    assert saved.oid == oid
    assert saved.recipient_id == recipient_id
    fake_transaction.commit.assert_awaited_once()
    fake_authorizer.require.assert_awaited_once()
    # Email goes out with the two-button payload; in-app/push via publish.
    notifier_kwargs = fake_notifier.send.call_args.kwargs
    assert NotificationChannel.EMAIL in notifier_kwargs["payloads"]
    fake_notifications.publish.assert_awaited_once()
    # Collaborators watching the editor get a ``gift_issued`` event.
    fake_event_bus.publish.assert_awaited_once()
    published = fake_event_bus.publish.call_args.args[0]
    assert isinstance(published.payload, GiftIssuedPayload)
    assert published.payload.gift_id == str(oid)


async def test_invite_by_user_rejects_owner(
    fake_transaction: AsyncMock,
    fake_entity_saver: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_notifier: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    security_config: object,
    product: Product,
    product_id: ProductID,
    actor_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = product
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_entity_saver=fake_entity_saver,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_gift_gateway=fake_gift_gateway,
        fake_notifier=fake_notifier,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
        security_config=security_config,
    )

    with pytest.raises(CannotGiftToOwnerError):
        await handler.run(
            InviteGiftByUserCommand(
                actor_id=actor_id,
                product_id=product_id,
                recipient_id=product.author_id,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()


async def test_invite_by_user_rejects_existing_gift(
    fake_transaction: AsyncMock,
    fake_entity_saver: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_notifier: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    security_config: object,
    product: Product,
    product_id: ProductID,
    actor_id: UserID,
    recipient_id: UserID,
    recipient_user: User,
    pending_gift: ProductGift,
) -> None:
    fake_product_gateway.with_id.return_value = product
    fake_user_gateway.with_id.return_value = recipient_user
    fake_gift_gateway.active_for_product_and_user.return_value = pending_gift
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_entity_saver=fake_entity_saver,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_gift_gateway=fake_gift_gateway,
        fake_notifier=fake_notifier,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
        security_config=security_config,
    )

    with pytest.raises(GiftAlreadyExistsError):
        await handler.run(
            InviteGiftByUserCommand(
                actor_id=actor_id,
                product_id=product_id,
                recipient_id=recipient_id,
            ),
        )


async def test_invite_by_user_rejects_non_note(
    fake_transaction: AsyncMock,
    fake_entity_saver: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_gift_gateway: AsyncMock,
    fake_notifier: AsyncMock,
    fake_notifications: AsyncMock,
    fake_event_bus: AsyncMock,
    security_config: object,
    product: Product,
    product_id: ProductID,
    actor_id: UserID,
    recipient_id: UserID,
) -> None:
    object.__setattr__(product, "type", _FakeWebinarType())
    fake_product_gateway.with_id.return_value = product
    handler = _build_handler(
        fake_transaction=fake_transaction,
        fake_entity_saver=fake_entity_saver,
        fake_authorizer=fake_authorizer,
        fake_product_gateway=fake_product_gateway,
        fake_user_gateway=fake_user_gateway,
        fake_gift_gateway=fake_gift_gateway,
        fake_notifier=fake_notifier,
        fake_notifications=fake_notifications,
        fake_event_bus=fake_event_bus,
        security_config=security_config,
    )

    with pytest.raises(ProductNotGiftableError):
        await handler.run(
            InviteGiftByUserCommand(
                actor_id=actor_id,
                product_id=product_id,
                recipient_id=recipient_id,
            ),
        )


class _FakeWebinarType:
    """Stand-in product type that is not NOTE (only NOTE exists today)."""

    value = "webinar"
