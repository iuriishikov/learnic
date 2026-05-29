from typing import Protocol

from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.models import CourseModule
from learnic.entities.product.ids import ProductID


class CourseModuleGateway(Protocol):
    """Write-side lookups and persistence for :class:`CourseModule`."""

    async def with_id(
        self,
        oid: CourseModuleID,
    ) -> CourseModule | None: ...

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[CourseModule]:
        """Return all modules of a course, ordered by position ascending."""
        ...

    async def lock_for_product(self, product_id: ProductID) -> None:
        """Take a transaction-scoped advisory lock on ``product_id``.

        Serializes module position mutations (add / reorder) within a
        course across replicas so concurrent editors cannot compute
        colliding ``position`` values or clobber each other's reorder.
        Call FIRST in every such handler. Auto-released on COMMIT /
        ROLLBACK. See :meth:`LessonBlockGateway.lock_for_lesson`.
        """
        ...

    async def delete(self, module: CourseModule) -> None: ...

    async def reorder(
        self,
        product_id: ProductID,
        ordered_ids: list[CourseModuleID],
    ) -> None:
        """Atomic full-reorder of all modules within a product.

        Caller must verify that ``ordered_ids`` is exactly the set
        of module ids belonging to the product. Implementation
        rewrites every row's ``position`` in one statement.
        """
        ...
