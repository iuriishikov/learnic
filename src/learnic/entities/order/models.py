import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.order.enums import OrderStatus
from learnic.entities.order.errors import OrderAlreadyRefundedError
from learnic.entities.order.ids import OrderID
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.entities.wallet.ids import FreezeEntryID
from learnic.entities.wallet.value_objects import MinorAmount, Money


@dataclass
class Order(BaseEntity[OrderID]):
    """A purchase record: student paid ``price`` for ``product``.

    ``commission_amount`` is the platform's per-mille cut at purchase
    time — stored as a snapshot so historical rows survive policy
    changes. The author's share is ``price.amount - commission_amount``;
    both shares are tracked as separate :class:`FreezeEntry` rows
    referenced by ``author_freeze_id`` / ``platform_freeze_id`` until
    the refund window closes.

    Status flips ``PAID → REFUNDED`` exactly once via :meth:`mark_refunded`.
    Whether a refund is allowed is decided by the caller from the
    referenced freezes — if either is no longer ``FROZEN`` the refund
    window is closed.
    """

    student_id: UserID
    product_id: ProductID
    price: Money
    commission_amount: MinorAmount
    author_freeze_id: FreezeEntryID
    platform_freeze_id: FreezeEntryID
    status: OrderStatus
    created_at: datetime
    refunded_at: datetime | None

    def mark_refunded(self, at: datetime) -> None:
        if self.status is OrderStatus.REFUNDED:
            raise OrderAlreadyRefundedError
        self.status = OrderStatus.REFUNDED
        self.refunded_at = at

    @classmethod
    def create(
        cls,
        student_id: UserID,
        product_id: ProductID,
        price: Money,
        commission_amount: MinorAmount,
        author_freeze_id: FreezeEntryID,
        platform_freeze_id: FreezeEntryID,
        created_at: datetime,
    ) -> Self:
        return cls(
            oid=OrderID(uuid.uuid4()),
            student_id=student_id,
            product_id=product_id,
            price=price,
            commission_amount=commission_amount,
            author_freeze_id=author_freeze_id,
            platform_freeze_id=platform_freeze_id,
            status=OrderStatus.PAID,
            created_at=created_at,
            refunded_at=None,
        )
