from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product.change_price import (
    ChangeProductPriceCommand,
    ChangeProductPriceCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.product_events import PriceChangedPayload
from learnic.entities.product.constants import (
    PRICE_AMOUNT_MAX,
    PRICE_AMOUNT_MIN,
)
from learnic.entities.product.errors import ProductPriceOutOfRangeError
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductPriceAmount
from learnic.entities.user.models import UserID


@pytest.fixture
def handler(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
) -> ChangeProductPriceCommandHandler:
    return ChangeProductPriceCommandHandler(
        transaction=fake_transaction,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )


async def test_owner_can_set_price_and_emits_event(
    handler: ChangeProductPriceCommandHandler,
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product

    await handler.run(
        ChangeProductPriceCommand(
            actor_id=author_id,
            product_id=course_product.oid,
            amount=500_00,
        ),
    )

    assert course_product.price == ProductPriceAmount(500_00)
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.payload == PriceChangedPayload(amount=500_00)
    assert event.product_id == course_product.oid
    assert event.actor_id == author_id


async def test_zero_amount_marks_product_free(
    handler: ChangeProductPriceCommandHandler,
    fake_product_gateway: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product

    await handler.run(
        ChangeProductPriceCommand(
            actor_id=author_id,
            product_id=course_product.oid,
            amount=0,
        ),
    )

    assert course_product.price == ProductPriceAmount(0)


async def test_non_owner_cannot_change_price(
    handler: ChangeProductPriceCommandHandler,
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            ChangeProductPriceCommand(
                actor_id=other_user_id,
                product_id=course_product.oid,
                amount=500_00,
            ),
        )

    assert course_product.price is None
    fake_transaction.commit.assert_not_awaited()
    fake_event_bus.publish.assert_not_awaited()


async def test_missing_product_raises(
    handler: ChangeProductPriceCommandHandler,
    fake_product_gateway: AsyncMock,
    author_id: UserID,
    course_product: Product,
) -> None:
    fake_product_gateway.with_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ChangeProductPriceCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                amount=500_00,
            ),
        )


async def test_amount_above_max_raises(
    handler: ChangeProductPriceCommandHandler,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product

    with pytest.raises(ProductPriceOutOfRangeError):
        await handler.run(
            ChangeProductPriceCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                amount=PRICE_AMOUNT_MAX + 1,
            ),
        )

    fake_event_bus.publish.assert_not_awaited()


async def test_negative_amount_raises(
    handler: ChangeProductPriceCommandHandler,
    fake_product_gateway: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product

    with pytest.raises(ProductPriceOutOfRangeError):
        await handler.run(
            ChangeProductPriceCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                amount=PRICE_AMOUNT_MIN - 1,
            ),
        )
