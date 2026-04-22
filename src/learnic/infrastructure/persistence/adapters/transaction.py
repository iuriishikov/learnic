from typing import Any, Final

from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import override

from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.common.base_entity import BaseEntity


class EntitySaverAlchemy(EntitySaver):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    def add_one(self, entity: BaseEntity[Any]) -> None:
        self._session.add(entity)


class TransactionAlchemy(Transaction):
    def __init__(self, session: AsyncSession) -> None:
        self._session: Final = session

    @override
    async def commit(self) -> None:
        await self._session.commit()

    @override
    async def rollback(self) -> None:
        await self._session.rollback()

    @override
    async def flush(self) -> None:
        await self._session.flush()
