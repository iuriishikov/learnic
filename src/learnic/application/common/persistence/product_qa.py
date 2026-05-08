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

    async def delete(self, qa: ProductQA) -> None: ...


class ProductQAReader(Protocol):
    """Read-side queries returning :class:`ProductQAView` projections."""

    async def for_product(
        self,
        product_id: ProductID,
    ) -> list[ProductQAView]: ...
