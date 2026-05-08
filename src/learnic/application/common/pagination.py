from dataclasses import dataclass
from typing import Final

DEFAULT_LIMIT: Final = 20
MAX_LIMIT: Final = 100


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
