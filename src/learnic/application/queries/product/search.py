from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import ProductReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product.get import (
    PaginatedProductsOutput,
    resolve_product_output,
)
from learnic.entities.tag.ids import TagID


@dataclass(slots=True, frozen=True)
class SearchPublishedProductsQuery:
    """Public-catalog search across name + author + tags + description.

    ``q`` is the raw user input — the reader trims and lower-cases
    it internally. Empty / whitespace-only queries are guarded at
    the HTTP boundary (``min_length=2``) and never reach this DTO.

    ``tag_ids`` intersects the full-text result with products
    carrying every requested tag (AND); empty = no tag filter, so
    search and the catalog's tag chips compose on one request.
    """

    q: str
    pagination: Pagination
    tag_ids: tuple[TagID, ...] = ()


@final
class SearchPublishedProductsQueryHandler:
    """Search the public catalog by free-text query.

    Delegates ranking entirely to the reader (the SQL is the
    interesting bit — weighted ``ts_rank_cd`` over the precomputed
    ``search_vector`` plus a ``pg_trgm`` similarity fallback for
    typos, both backed by GIN indexes). Output shape matches
    :class:`GetPublishedProductsQueryHandler` — same
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
        data: SearchPublishedProductsQuery,
    ) -> PaginatedProductsOutput:
        views = await self._reader.search_published(
            data.q, data.pagination, data.tag_ids,
        )
        total = await self._reader.search_published_count(
            data.q, data.tag_ids,
        )
        items = [
            await resolve_product_output(view, self._file_storage)
            for view in views
        ]
        return PaginatedProductsOutput(items=items, total=total)
