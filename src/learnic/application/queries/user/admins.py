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
from learnic.application.queries.user.search import UserSummaryOutput


@dataclass(slots=True, frozen=True)
class GetAdminsQuery:
    """List the platform's administrator accounts.

    Powers public "our team" surfaces (e.g. the landing-page support
    block), so only the shared identity projection leaves the
    application layer — masked email, display name, verified badge,
    avatar. Banned admins are excluded; the query carries only
    pagination.
    """

    pagination: Pagination


@final
class GetAdminsQueryHandler:
    def __init__(
        self,
        reader: UserReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetAdminsQuery) -> list[UserSummaryOutput]:
        views = await self._reader.admins(pagination=data.pagination)
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
