from typing import Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.product_qa import (
    ProductQAGateway,
    ProductQAReader,
    ProductQAView,
)
from learnic.entities.product.ids import ProductID, ProductQAID
from learnic.entities.product.qa import ProductQA
from learnic.infrastructure.persistence.models.product import (
    product_qa_table,
)


class ProductQAMapperAlchemy(ProductQAGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def with_id(self, oid: ProductQAID) -> ProductQA | None:
        stmt = sa.select(ProductQA).where(product_qa_table.c.oid == oid)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[ProductQA]:
        stmt = (
            sa.select(ProductQA)
            .where(product_qa_table.c.product_id == product_id)
            .order_by(product_qa_table.c.position.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def count_for_product(self, product_id: ProductID) -> int:
        stmt = (
            sa.select(sa.func.count())
            .select_from(product_qa_table)
            .where(product_qa_table.c.product_id == product_id)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    @override
    async def delete(self, qa: ProductQA) -> None:
        await self._session.delete(qa)


class ProductQAReaderAlchemy(ProductQAReader):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[ProductQAView]:
        stmt = (
            sa.select(
                product_qa_table.c.oid,
                product_qa_table.c.product_id,
                product_qa_table.c.question,
                product_qa_table.c.answer,
                product_qa_table.c.position,
            )
            .where(product_qa_table.c.product_id == product_id)
            .order_by(product_qa_table.c.position.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            ProductQAView(
                oid=ProductQAID(row.oid),
                product_id=ProductID(row.product_id),
                question=row.question,
                answer=row.answer,
                position=row.position,
            )
            for row in rows
        ]
