from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import ProductReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product.get import (
    PaginatedProductsOutput,
    resolve_product_output,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SearchMyProductsQuery:
    """Free-text search across the caller's accessible products.

    ``q`` is the raw user input — the reader trims and lower-cases
    it internally. Empty / whitespace-only queries are guarded at
    the HTTP boundary (``min_length=2``) and never reach this DTO.
    """

    user_id: UserID
    q: str
    pagination: Pagination


@final
class SearchMyProductsQueryHandler:
    """Search the caller's accessible products by free-text query.

    Membership rule matches :class:`GetMyProductsQueryHandler`
    (author OR active collaborator, any product status). Ranking
    delegates entirely to the reader — same weighted ``ts_rank_cd``
    over the precomputed ``search_vector`` plus a ``pg_trgm``
    similarity fallback used by the public-catalog search, so
    relevance behaviour is consistent across both surfaces.
    Output shape matches the list-mode handler — same
    :class:`PaginatedProductsOutput` — so the HTTP layer can route
    either handler to the same response schema without branching.
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
        data: SearchMyProductsQuery,
    ) -> PaginatedProductsOutput:
        views = await self._reader.search_accessible_to(
            data.user_id, data.q, data.pagination,
        )
        total = await self._reader.search_accessible_to_count(
            data.user_id, data.q,
        )
        items = [
            await resolve_product_output(view, self._file_storage)
            for view in views
        ]
        return PaginatedProductsOutput(items=items, total=total)
