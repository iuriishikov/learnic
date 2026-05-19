from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.entities.order.enums import OrderStatus
from learnic.entities.order.ids import OrderID
from learnic.entities.order.models import Order
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.ids import FreezeEntryID


@dataclass(slots=True, frozen=True)
class OrderView:
    """Read-side projection of :class:`Order`."""

    oid: OrderID
    student_id: UserID
    product_id: ProductID
    price_amount: int
    price_currency: Currency
    commission_amount: int
    author_freeze_id: FreezeEntryID
    platform_freeze_id: FreezeEntryID
    status: OrderStatus
    created_at: datetime
    refunded_at: datetime | None


class OrderGateway(Protocol):
    """Write-side lookups for :class:`Order`."""

    async def with_id(self, oid: OrderID) -> Order | None: ...

    async def with_id_locked(self, oid: OrderID) -> Order | None: ...


class OrderReader(Protocol):
    """Read-side queries returning :class:`OrderView` projections."""

    async def with_id(self, oid: OrderID) -> OrderView | None: ...
