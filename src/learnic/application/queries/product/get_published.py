from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import (
    ProductReader,
    ProductView,
)


@dataclass(slots=True, frozen=True)
class GetPublishedProductsQuery:
    pagination: Pagination


@final
class GetPublishedProductsQueryHandler:
    """Public catalog — all products with status ``PUBLISHED``."""

    def __init__(self, reader: ProductReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: GetPublishedProductsQuery,
    ) -> list[ProductView]:
        return await self._reader.published(data.pagination)
