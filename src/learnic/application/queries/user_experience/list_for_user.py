from dataclasses import dataclass
from datetime import date
from typing import Final, final

from learnic.application.common.persistence.file import FileView
from learnic.application.common.persistence.user_experience import (
    UserExperienceReader,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.ids import UserExperienceID


@dataclass(slots=True, frozen=True)
class ListUserExperiencesQuery:
    user_id: UserID


@dataclass(slots=True, frozen=True)
class UserExperienceOutput:
    """Single experience row with the icon URL already resolved.

    ``icon`` carries a presigned :class:`FileView`; Pydantic schemas
    auto-map it through ``from_attributes=True``. URLs are short-
    lived — clients should refetch the list to refresh rather than
    caching the value.
    """

    oid: UserExperienceID
    user_id: UserID
    title: str
    description: str | None
    start_date: date
    end_date: date | None
    source_url: str | None
    icon: FileView | None


@final
class ListUserExperiencesQueryHandler:
    """Returns experiences for a user, newest start date first."""

    def __init__(
        self,
        reader: UserExperienceReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: ListUserExperiencesQuery,
    ) -> list[UserExperienceOutput]:
        views = await self._reader.for_user(data.user_id)
        return [
            UserExperienceOutput(
                oid=view.oid,
                user_id=view.user_id,
                title=view.title,
                description=view.description,
                start_date=view.start_date,
                end_date=view.end_date,
                source_url=view.source_url,
                icon=await FileView.of_optional(view.icon, self._file_storage),
            )
            for view in views
        ]
