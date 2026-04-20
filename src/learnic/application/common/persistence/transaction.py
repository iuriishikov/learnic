from typing import Any, Protocol

from learnic.entities.common.base_entity import BaseEntity


class EntitySaver(Protocol):
    def add_one(self, entity: BaseEntity[Any]) -> None: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
