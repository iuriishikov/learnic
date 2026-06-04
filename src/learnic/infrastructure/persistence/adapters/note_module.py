from typing import Any, Final

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.note_module import (
    NoteModuleGateway,
)
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_module.models import NoteModule
from learnic.entities.product.ids import ProductID
from learnic.infrastructure.persistence.models.note_module import (
    note_modules_table,
)


class NoteModuleMapperAlchemy(NoteModuleGateway):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def lock_for_product(self, product_id: ProductID) -> None:
        await self._session.execute(
            sa.text(
                "SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))",
            ),
            {"k": str(product_id)},
        )

    @override
    async def with_id(
        self,
        oid: NoteModuleID,
    ) -> NoteModule | None:
        stmt = sa.select(NoteModule).where(
            note_modules_table.c.oid == oid,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[NoteModule]:
        stmt = (
            sa.select(NoteModule)
            .where(note_modules_table.c.product_id == product_id)
            .order_by(note_modules_table.c.position.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def delete(self, module: NoteModule) -> None:
        await self._session.delete(module)

    @override
    async def reorder(
        self,
        product_id: ProductID,
        ordered_ids: list[NoteModuleID],
    ) -> None:
        if not ordered_ids:
            return
        whens: dict[Any, int] = {oid: idx for idx, oid in enumerate(ordered_ids)}
        case_expr = sa.case(whens, value=note_modules_table.c.oid)
        stmt = (
            sa.update(note_modules_table)
            .where(note_modules_table.c.product_id == product_id)
            .where(note_modules_table.c.oid.in_(ordered_ids))
            .values(position=case_expr)
        )
        await self._session.execute(stmt)
