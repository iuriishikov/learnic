from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.tag import TagReader, TagView


@dataclass(slots=True, frozen=True)
class GetPopularTagsQuery:
    """Input to ``GET /tags/popular``.

    ``limit`` is enforced at the HTTP boundary (capped against a
    sensible default so a misbehaving client cannot ask for the whole
    tag pool); the handler trusts the validated value it receives.
    """

    limit: int


@final
class GetPopularTagsQueryHandler:
    """Return the most-used tags across published products.

    Backs the marketplace "popular tags" filter row. One SQL
    aggregate via :meth:`TagReader.popular` — no product fetch, no
    SPA-side aggregation, no per-product fan-out.
    """

    def __init__(self, reader: TagReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetPopularTagsQuery) -> list[TagView]:
        return await self._reader.popular(data.limit)
