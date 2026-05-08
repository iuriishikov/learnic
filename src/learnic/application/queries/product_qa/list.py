from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.product_qa import (
    ProductQAReader,
    ProductQAView,
)
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class GetProductQAListQuery:
    product_id: ProductID


@final
class GetProductQAListQueryHandler:
    """Returns Q&A entries attached to a product, ordered by position."""

    def __init__(self, reader: ProductQAReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetProductQAListQuery,
    ) -> list[ProductQAView]:
        return await self._reader.for_product(data.product_id)
