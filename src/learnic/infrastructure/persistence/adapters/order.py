from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.order import (
    OrderGateway,
    OrderReader,
    OrderView,
)
from learnic.entities.order.enums import OrderStatus
from learnic.entities.order.ids import OrderID
from learnic.entities.order.models import Order
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.entities.wallet.enums import Currency
from learnic.entities.wallet.ids import FreezeEntryID
from learnic.infrastructure.persistence.models.order import orders_table


class OrderMapperAlchemy(OrderGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: OrderID) -> Order | None:
        stmt = sa.select(Order).where(orders_table.c.oid == oid)
        return (await self._session.execute(stmt)).scalar_one_or_none()

    @override
    async def with_id_locked(self, oid: OrderID) -> Order | None:
        stmt = (
            sa.select(Order)
            .where(orders_table.c.oid == oid)
            .with_for_update()
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()


class OrderReaderAlchemy(OrderReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: OrderID) -> OrderView | None:
        stmt = sa.select(
            orders_table.c.oid,
            orders_table.c.student_id,
            orders_table.c.product_id,
            orders_table.c.price_amount,
            orders_table.c.price_currency,
            orders_table.c.commission_amount,
            orders_table.c.author_freeze_id,
            orders_table.c.platform_freeze_id,
            orders_table.c.status,
            orders_table.c.created_at,
            orders_table.c.refunded_at,
        ).where(orders_table.c.oid == oid)
        row = (await self._session.execute(stmt)).one_or_none()
        if row is None:
            return None
        return OrderView(
            oid=OrderID(row.oid),
            student_id=UserID(row.student_id),
            product_id=ProductID(row.product_id),
            price_amount=int(row.price_amount),
            price_currency=Currency(row.price_currency),
            commission_amount=int(row.commission_amount),
            author_freeze_id=FreezeEntryID(row.author_freeze_id),
            platform_freeze_id=FreezeEntryID(row.platform_freeze_id),
            status=OrderStatus(row.status),
            created_at=row.created_at,
            refunded_at=row.refunded_at,
        )
