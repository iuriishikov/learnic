from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class LessonLineage:
    """Resolved ancestor ids for a lesson target.

    Used by ``Authorizer`` to decide which module-scoped grants
    cover a lesson-level target without forcing the caller to
    pass module + product ids on every check (the lineage reader
    fills them in from a single SQL).
    """

    lesson_id: UUID
    module_id: UUID
    product_id: ProductID


@dataclass(slots=True, frozen=True)
class ModuleLineage:
    module_id: UUID
    product_id: ProductID


class ResourceLineageReader(Protocol):
    """Read-side resolver for resource ancestor relationships."""

    async def lineage_for_lesson(
        self,
        lesson_id: UUID,
    ) -> LessonLineage | None: ...

    async def lineage_for_module(
        self,
        module_id: UUID,
    ) -> ModuleLineage | None: ...
