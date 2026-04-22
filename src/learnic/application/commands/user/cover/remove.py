from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RemoveUserCoverCommand:
    user_id: UserID


@final
class RemoveUserCoverCommandHandler:
    """Detaches cover from user and soft-deletes the file row."""

    def __init__(
        self,
        transaction: Transaction,
        user_gateway: UserGateway,
        files_gateway: FilesGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._user_gateway: Final = user_gateway
        self._files_gateway: Final = files_gateway

    async def run(self, data: RemoveUserCoverCommand) -> None:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)

        previous_file_id = user.remove_cover()
        if previous_file_id is not None:
            previous_file = await self._files_gateway.with_id(previous_file_id)
            if previous_file is not None and not previous_file.is_deleted:
                previous_file.mark_deleted()
        await self._transaction.commit()
