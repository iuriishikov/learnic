from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import ProductReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product.get import (
    ProductOutput,
    resolve_product_output,
)


@dataclass(slots=True, frozen=True)
class GetPublishedProductsQuery:
    pagination: Pagination


@final
class GetPublishedProductsQueryHandler:
    """Public catalog — all products with status ``PUBLISHED``.

    Cover URLs are presigned per row so the SPA can render thumbnails
    directly without an extra round-trip.
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
    ) -> list[ProductOutput]:
        views = await self._reader.published(data.pagination)
        return [
            await resolve_product_output(view, self._file_storage)
            for view in views
        ]
