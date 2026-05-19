from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.tag import TagReader, TagView
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class ListProductTagsQuery:
    """Input to ``GET /products/{product_id}/tags`` and embedded reads."""

    product_id: ProductID


@final
class ListProductTagsQueryHandler:
    """Return the product's tags in author-defined order.

    No authorization check: tag visibility tracks product
    visibility — the product endpoint that called this handler
    has already gated read access. Embedding this list in
    ``GET /products/{id}`` avoids a second SPA request.
    """

    def __init__(self, reader: TagReader) -> None:
        self._reader: Final = reader

    async def run(self, data: ListProductTagsQuery) -> list[TagView]:
        return await self._reader.for_product(data.product_id)
