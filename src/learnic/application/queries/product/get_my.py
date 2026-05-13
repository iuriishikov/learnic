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
class GetMyProductsQuery:
    user_id: UserID
    pagination: Pagination


@final
class GetMyProductsQueryHandler:
    """Returns products the user can access (owned or active collaboration).

    A product appears in the result if ``user_id`` is its author or
    has an active collaboration on it. ``PENDING_INVITE`` and
    ``REVOKED`` collaborations are excluded. Results are ordered by
    ``created_at`` descending (any product status). Cover URLs are
    presigned per row so the SPA can render thumbnails directly.
    """

    def __init__(
        self,
        reader: ProductReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetMyProductsQuery) -> list[ProductOutput]:
        views = await self._reader.accessible_to(
            data.user_id,
            data.pagination,
        )
        return [
            await resolve_product_output(view, self._file_storage)
            for view in views
        ]
