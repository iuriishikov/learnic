from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import UserAvatarNotFoundError
from learnic.application.common.persistence.user import UserReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.validators import validate_empty
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserAvatarQuery:
    oid: UserID


@dataclass(slots=True, frozen=True)
class UserAvatarOutput:
    """Query result for a user's avatar.

    The handler only returns a value when the user has an avatar
    attached; otherwise it raises ``UserAvatarNotFoundError``.
    """

    url: str


@final
class GetUserAvatarQueryHandler:
    def __init__(
        self,
        reader: UserReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetUserAvatarQuery) -> UserAvatarOutput:
        view = validate_empty(await self._reader.with_id(data.oid), data.oid)
        if view.avatar is None:
            raise UserAvatarNotFoundError
        url = await self._file_storage.presigned_get_url(
            view.avatar.bucket, view.avatar.storage_name
        )
        return UserAvatarOutput(url=url)
