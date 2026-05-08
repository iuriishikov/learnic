from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.auth.role_hierarchy import (
    ProductOwnerResolver,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID
from learnic.infrastructure.persistence.models.product import products_table


class ProductOwnerResolverAlchemy(ProductOwnerResolver):
    """SQL-backed :class:`ProductOwnerResolver`.

    One small ``SELECT`` against ``products.author_id``. Mirrors
    the logic already in :class:`AuthorizerService._is_product_owner`
    so the two checks stay consistent.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def is_owner(
        self,
        product_id: ProductID,
        user_id: UserID,
    ) -> bool:
        stmt = sa.select(products_table.c.author_id).where(
            products_table.c.oid == product_id,
        )
        row = (await self._session.execute(stmt)).one_or_none()
        return row is not None and row.author_id == user_id
