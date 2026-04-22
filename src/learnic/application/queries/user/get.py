from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.user import UserReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.validators import validate_empty
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserQuery:
    oid: UserID


@dataclass(slots=True, frozen=True)
class UserOutput:
    """Query result with media URLs already resolved."""

    oid: UserID
    email: str
    first_name: str
    last_name: str
    patronymic: str | None
    avatar_url: str | None
    cover_url: str | None


@final
class GetUserQueryHandler:
    def __init__(
        self,
        reader: UserReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetUserQuery) -> UserOutput:
        view = validate_empty(await self._reader.with_id(data.oid), data.oid)

        avatar_url: str | None = None
        if view.avatar is not None:
            avatar_url = await self._file_storage.presigned_get_url(
                view.avatar.bucket, view.avatar.storage_name
            )

        cover_url: str | None = None
        if view.cover is not None:
            cover_url = await self._file_storage.presigned_get_url(
                view.cover.bucket, view.cover.storage_name
            )

        return UserOutput(
            oid=view.oid,
            email=view.email,
            first_name=view.first_name,
            last_name=view.last_name,
            patronymic=view.patronymic,
            avatar_url=avatar_url,
            cover_url=cover_url,
        )
