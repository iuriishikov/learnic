from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.formatting import (
    build_full_name,
    mask_email,
)
from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.file import FileView
from learnic.application.common.persistence.teacher_ranking import (
    TeacherRankingReader,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetTopTeachersQuery:
    """List the platform's users ranked by teaching popularity.

    "Popular" means most distinct active students across the user's
    published products — see :class:`TopTeacherView` for the exact
    metric semantics. Every registered (non-banned) user is included;
    those with no students fall to the tail. The query carries only
    pagination; the ranking rule is fixed in the reader.
    """

    pagination: Pagination


@dataclass(slots=True, frozen=True)
class TopTeacherOutput:
    """Single ranked-user row with its avatar URL already resolved.

    ``full_name`` collapses the user's name parts into the canonical
    Russian-style display name (``Last First Patronymic``). ``email``
    is already masked via :func:`mask_email`, so the projection never
    carries a plain address. ``avatar`` carries a resolved
    :class:`FileView` with a short-lived presigned URL; Pydantic
    schemas auto-map it through ``from_attributes=True``.
    ``student_count`` / ``published_product_count`` are the ranking
    metrics (``0`` for a user who has taught nothing), surfaced so the
    UI can render them next to the user.
    """

    oid: UserID
    full_name: str
    email: str
    is_verified: bool
    avatar: FileView | None
    student_count: int
    published_product_count: int


@final
class GetTopTeachersQueryHandler:
    def __init__(
        self,
        reader: TeacherRankingReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: GetTopTeachersQuery,
    ) -> list[TopTeacherOutput]:
        views = await self._reader.top_by_students(
            pagination=data.pagination,
        )
        return [
            TopTeacherOutput(
                oid=view.oid,
                full_name=build_full_name(
                    view.first_name, view.last_name, view.patronymic,
                ),
                email=mask_email(view.email),
                is_verified=view.is_verified,
                avatar=await FileView.of_optional(
                    view.avatar, self._file_storage,
                ),
                student_count=view.student_count,
                published_product_count=view.published_product_count,
            )
            for view in views
        ]
