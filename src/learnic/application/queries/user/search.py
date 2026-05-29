from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.formatting import (
    build_full_name,
    mask_email,
)
from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileView
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
    """Single search hit.

    ``full_name`` collapses the user's name fields into the
    canonical Russian-style display name (``Last First Patronymic``)
    so callers can render a result row without re-joining the parts
    themselves. ``email`` is already masked via :func:`mask_email`,
    so the projection never carries a plain address. ``avatar``
    carries a resolved :class:`FileView` with a short-lived presigned
    URL; Pydantic schemas auto-map it through ``from_attributes=True``.
    """

    oid: UserID
    full_name: str
    email: str
    is_verified: bool
    avatar: FileView | None


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
        return [
            UserSummaryOutput(
                oid=view.oid,
                full_name=build_full_name(
                    view.first_name, view.last_name, view.patronymic
                ),
                email=mask_email(view.email),
                is_verified=view.is_verified,
                avatar=await FileView.of_optional(
                    view.avatar, self._file_storage,
                ),
            )
            for view in views
        ]

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
