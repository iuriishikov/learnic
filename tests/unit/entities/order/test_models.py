import uuid
from datetime import datetime, timezone

import pytest

from learnic.entities.order.enums import OrderStatus
from learnic.entities.order.errors import OrderAlreadyRefundedError
from learnic.entities.order.models import Order
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.ids import FreezeEntryID
from learnic.entities.wallet.value_objects import MinorAmount, Money


def _make_order() -> Order:
    return Order.create(
        student_id=UserID(uuid.uuid4()),
        product_id=ProductID(uuid.uuid4()),
        price=Money(MinorAmount(500_00), Currency.RUB),
        commission_amount=MinorAmount(50_00),
        author_freeze_id=FreezeEntryID(uuid.uuid4()),
        platform_freeze_id=FreezeEntryID(uuid.uuid4()),
        created_at=datetime.now(timezone.utc),
    )


class TestCreate:
    def test_starts_paid(self) -> None:
        assert _make_order().status is OrderStatus.PAID

    def test_refunded_at_starts_none(self) -> None:
        assert _make_order().refunded_at is None


class TestMarkRefunded:
    def test_marks_paid_order_refunded(self) -> None:
        order = _make_order()
        at = datetime.now(timezone.utc)
        order.mark_refunded(at)
        assert order.status is OrderStatus.REFUNDED
        assert order.refunded_at == at

    def test_double_refund_raises(self) -> None:
        order = _make_order()
        order.mark_refunded(datetime.now(timezone.utc))
        with pytest.raises(OrderAlreadyRefundedError):
            order.mark_refunded(datetime.now(timezone.utc))
