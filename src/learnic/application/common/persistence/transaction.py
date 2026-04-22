from typing import Any, Protocol

from learnic.entities.common.base_entity import BaseEntity


class EntitySaver(Protocol):
    def add_one(self, entity: BaseEntity[Any]) -> None: ...


class Transaction(Protocol):
    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    async def flush(self) -> None:
        """Emit pending ORM changes to the DB without committing.

        Use when a downstream Core statement (INSERT/UPDATE) needs the
        row from a freshly-added entity to exist in the current
        transaction — e.g. to satisfy a foreign key. The transaction
        remains open; ``commit()`` or ``rollback()`` is still required.
        """
        ...
