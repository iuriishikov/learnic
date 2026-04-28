from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import UserCoverNotFoundError
from learnic.application.common.persistence.user import UserReader
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.validators import validate_empty
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetUserCoverQuery:
    oid: UserID


@dataclass(slots=True, frozen=True)
class UserCoverOutput:
    """Query result for a user's cover.

    The handler only returns a value when the user has a cover
    attached; otherwise it raises ``UserCoverNotFoundError``.
    """

    url: str


@final
class GetUserCoverQueryHandler:
    def __init__(
        self,
        reader: UserReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetUserCoverQuery) -> UserCoverOutput:
        view = validate_empty(await self._reader.with_id(data.oid), data.oid)
        if view.cover is None:
            raise UserCoverNotFoundError
        url = await self._file_storage.presigned_get_url(
            view.cover.bucket, view.cover.storage_name
        )
        return UserCoverOutput(url=url)
