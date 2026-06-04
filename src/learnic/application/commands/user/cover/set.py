from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.application.common.storage.upload import IncomingUpload
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class SetUserCoverCommand:
    user_id: UserID
    upload: IncomingUpload


@final
class SetUserCoverCommandHandler:
    """Uploads a new cover image, attaches it, soft-deletes the old one."""

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        file_uploads: FileUploadService,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._file_uploads: Final = file_uploads

    async def run(self, data: SetUserCoverCommand) -> FileID:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)

        file = await self._file_uploads.upload_stream(
            data.upload,
            data.user_id,
        )
        previous_file_id = user.set_cover(file.oid)
        await self._file_uploads.soft_delete_previous(previous_file_id)

        await self._transaction.commit()
        return file.oid
