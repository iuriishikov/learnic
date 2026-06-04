from typing import Protocol

from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_module.models import NoteModule
from learnic.entities.product.ids import ProductID


class NoteModuleGateway(Protocol):
    """Write-side lookups and persistence for :class:`NoteModule`."""

    async def with_id(
        self,
        oid: NoteModuleID,
    ) -> NoteModule | None: ...

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[NoteModule]:
        """Return all modules of a note, ordered by position ascending."""
        ...

    async def lock_for_product(self, product_id: ProductID) -> None:
        """Take a transaction-scoped advisory lock on ``product_id``.

        Serializes module position mutations (add / reorder) within a
        note across replicas so concurrent editors cannot compute
        colliding ``position`` values or clobber each other's reorder.
        Call FIRST in every such handler. Auto-released on COMMIT /
        ROLLBACK. See :meth:`LessonBlockGateway.lock_for_lesson`.
        """
        ...

    async def delete(self, module: NoteModule) -> None: ...

    async def reorder(
        self,
        product_id: ProductID,
        ordered_ids: list[NoteModuleID],
    ) -> None:
        """Atomic full-reorder of all modules within a product.

        Caller must verify that ``ordered_ids`` is exactly the set
        of module ids belonging to the product. Implementation
        rewrites every row's ``position`` in one statement.
        """
        ...
