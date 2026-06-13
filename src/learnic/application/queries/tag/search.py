from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.tag import TagReader, TagView


@dataclass(slots=True, frozen=True)
class SearchTagsQuery:
    """Input to ``GET /tags``.

    ``query`` is the text typed in the SPA combobox. A non-empty value
    runs a full-text + ``pg_trgm`` fuzzy match over the tag ``name``
    (same engine as user/product search — morphology + typo tolerance);
    an empty value returns the full pool name-ordered. Pagination
    defaults are applied at the HTTP boundary.
    """

    query: str
    pagination: Pagination


@final
class SearchTagsQueryHandler:
    """Autocomplete tags by full-text + trigram-fuzzy name match.

    No authorization gate beyond an active session — every
    authenticated user may inspect the global tag pool, since the
    SPA needs the autocomplete to suggest tags created by other
    authors. Cookie auth runs at the HTTP boundary; this handler
    has no actor to check.
    """

    def __init__(self, reader: TagReader) -> None:
        self._reader: Final = reader

    async def run(self, data: SearchTagsQuery) -> list[TagView]:
        return await self._reader.search(data.query, data.pagination)
