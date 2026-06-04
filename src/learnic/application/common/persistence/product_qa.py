from dataclasses import dataclass
from typing import Protocol

from learnic.entities.product.ids import ProductID, ProductQAID
from learnic.entities.product.qa import ProductQA


@dataclass(slots=True, frozen=True)
class ProductQAView:
    """Read-side projection of :class:`ProductQA`."""

    oid: ProductQAID
    product_id: ProductID
    question: str
    answer: str
    position: int


class ProductQAGateway(Protocol):
    """Write-side lookups for :class:`ProductQA`."""

    async def with_id(self, oid: ProductQAID) -> ProductQA | None: ...

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[ProductQA]: ...

    async def count_for_product(self, product_id: ProductID) -> int:
        """Return how many Q&A entries ``product_id`` already has.

        Used by ``AddProductQACommandHandler`` to enforce
        :data:`PRODUCT_QA_LIMIT` — an abuse guard so the
        unpaginated public ``GET /products/{id}/qa`` cannot be
        inflated without bound.
        """
        ...

    async def delete(self, qa: ProductQA) -> None: ...


class ProductQAReader(Protocol):
    """Read-side queries returning :class:`ProductQAView` projections."""

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[ProductQAView]: ...
