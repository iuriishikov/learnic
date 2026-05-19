from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import ProductReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product.get import (
    PaginatedProductsOutput,
    resolve_product_output,
)


@dataclass(slots=True, frozen=True)
class GetPublishedProductsQuery:
    pagination: Pagination


@final
class GetPublishedProductsQueryHandler:
    """Public catalog — all products with status ``PUBLISHED``.

    Returns a :class:`PaginatedProductsOutput` with both the page
    of items (cover URLs presigned per row) and the total match
    count so the SPA can render numbered page controls.
    """

    def __init__(
        self,
        reader: ProductReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: GetPublishedProductsQuery,
    ) -> PaginatedProductsOutput:
        views = await self._reader.published(data.pagination)
        total = await self._reader.published_count()
        items = [
            await resolve_product_output(view, self._file_storage)
            for view in views
        ]
        return PaginatedProductsOutput(items=items, total=total)
