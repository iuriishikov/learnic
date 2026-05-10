from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.formatting import build_full_name
from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.user import UserReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.user.models import UserID

MIN_QUERY_LEN: Final = 2
MAX_TOKENS: Final = 5


@dataclass(slots=True, frozen=True)
class SearchUsersQuery:
    """Free-text search over registered users by name fields.

    The query string is whitespace-tokenized; each token must match
    (case-insensitive substring) at least one of ``first_name`` /
    ``last_name`` / ``patronymic``. Empty / whitespace-only inputs
    return an empty list without touching the database.
    """

    query: str
    pagination: Pagination


@dataclass(slots=True, frozen=True)
class UserSummaryOutput:
    """Single search hit. Email is intentionally absent.

    ``full_name`` collapses the user's name fields into the
    canonical Russian-style display name (``Last First Patronymic``)
    so callers can render a result row without re-joining the parts
    themselves. The avatar URL is resolved by the handler to a
    short-lived presigned URL; clients render it directly.
    """

    oid: UserID
    full_name: str
    avatar_url: str | None


@final
class SearchUsersQueryHandler:
    def __init__(
        self,
        reader: UserReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: SearchUsersQuery) -> list[UserSummaryOutput]:
        tokens = self._tokenize(data.query)
        if not tokens:
            return []

        views = await self._reader.search_by_name(
            tokens=tokens,
            pagination=data.pagination,
        )

        results: list[UserSummaryOutput] = []
        for view in views:
            avatar_url: str | None = None
            if view.avatar is not None:
                avatar_url = await self._file_storage.presigned_get_url(
                    view.avatar.bucket,
                    view.avatar.storage_name,
                )
            results.append(
                UserSummaryOutput(
                    oid=view.oid,
                    full_name=build_full_name(
                        view.first_name, view.last_name, view.patronymic
                    ),
                    avatar_url=avatar_url,
                )
            )
        return results

    @staticmethod
    def _tokenize(query: str) -> tuple[str, ...]:
        seen: set[str] = set()
        tokens: list[str] = []
        for raw in query.split():
            token = raw.strip()
            if len(token) < MIN_QUERY_LEN:
                continue
            lowered = token.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            tokens.append(token)
            if len(tokens) >= MAX_TOKENS:
                break
        return tuple(tokens)
