from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import ProductReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product.get import (
    ProductOutput,
    resolve_product_output,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserProductsQuery:
    """List published products authored by ``user_id``.

    Powers the public profile page's "products" rail. The handler
    presigns cover URLs per row so the SPA can render thumbnails
    directly without an extra round-trip.
    """

    user_id: UserID
    pagination: Pagination


@final
class GetUserProductsQueryHandler:
    def __init__(
        self,
        reader: ProductReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: GetUserProductsQuery,
    ) -> list[ProductOutput]:
        views = await self._reader.published_by_author(
            author_id=data.user_id,
            pagination=data.pagination,
        )
        return [
            await resolve_product_output(view, self._file_storage)
            for view in views
        ]
