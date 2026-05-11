from dataclasses import dataclass
from datetime import date
from typing import Final, final

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
    """Single experience row with the icon URL resolved.

    ``icon_url`` is a short-lived presigned URL; clients should
    refetch the list to refresh it rather than caching the value.
    """

    oid: UserExperienceID
    user_id: UserID
    title: str
    description: str | None
    start_date: date
    end_date: date | None
    source_url: str | None
    icon_url: str | None


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
        results: list[UserExperienceOutput] = []
        for view in views:
            icon_url: str | None = None
            if view.icon is not None:
                icon_url = await self._file_storage.presigned_get_url(
                    view.icon.bucket,
                    view.icon.storage_name,
                )
            results.append(
                UserExperienceOutput(
                    oid=view.oid,
                    user_id=view.user_id,
                    title=view.title,
                    description=view.description,
                    start_date=view.start_date,
                    end_date=view.end_date,
                    source_url=view.source_url,
                    icon_url=icon_url,
                ),
            )
        return results
