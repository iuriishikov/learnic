from dataclasses import dataclass
from typing import Final

DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 100

# Free-text search query bounds. Lives next to pagination because
# both are cross-cutting list-query inputs validated identically at
# the HTTP boundary (Pydantic ``Query(min_length=..., max_length=...)``).
# Min length 2 keeps single-character lookups out of full-table scans;
# max length is a safety cap, real queries are far shorter.
SEARCH_QUERY_MIN_LEN: Final = 2
SEARCH_QUERY_MAX_LEN: Final = 100


@dataclass(slots=True, frozen=True)
class Pagination:
    """Offset-based pagination parameters for list queries.

    Validation lives at the HTTP boundary — Pydantic ``Field`` /
    ``Query`` enforces ``offset >= 0`` and ``1 <= limit <= MAX_LIMIT``
    before the application layer ever sees the values. The
    application layer trusts whatever it receives.
    """

    limit: int = DEFAULT_LIMIT
    offset: int = 0
