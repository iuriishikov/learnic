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


@dataclass(slots=True, frozen=True)
class SearchUsersQuery:
    """Full-text + fuzzy search over registered users by name fields.

    Backed by a Postgres ``tsvector`` (Russian morphology, weighted
    ``last_name`` > ``first_name`` > ``patronymic``) with a ``pg_trgm``
    word-similarity fallback for typos — the same engine as the product
    catalog search. Inputs shorter than ``MIN_QUERY_LEN`` (after trim)
    return an empty list without touching the index.
    """

    query: str
    pagination: Pagination


@dataclass(slots=True, frozen=True)
class UserSummaryOutput:
    """Single search hit; also reused by the admins-list query.

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
    is_banned: bool
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
        # Postgres does the tokenization (``websearch_to_tsquery``) and
        # fuzzy matching; the handler only enforces the minimum length so
        # a 1-char query doesn't hammer the trigram index with noise.
        stripped = data.query.strip()
        if len(stripped) < MIN_QUERY_LEN:
            return []

        views = await self._reader.search_by_name(
            query=stripped,
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
                is_banned=view.is_banned,
                avatar=await FileView.of_optional(
                    view.avatar, self._file_storage,
                ),
            )
            for view in views
        ]
