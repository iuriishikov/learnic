from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.file import FilesGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user_experience import (
    UserExperienceGateway,
)
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.ids import UserExperienceID


@dataclass(slots=True, frozen=True)
class RemoveUserExperienceIconCommand:
    actor_id: UserID
    experience_id: UserExperienceID


@final
class RemoveUserExperienceIconCommandHandler:
    """Detaches the icon and soft-deletes the underlying file row."""

    def __init__(
        self,
        transaction: Transaction,
        experience_gateway: UserExperienceGateway,
        files_gateway: FilesGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._experience_gateway: Final = experience_gateway
        self._files_gateway: Final = files_gateway

    async def run(self, data: RemoveUserExperienceIconCommand) -> None:
        experience = await self._experience_gateway.with_id(
            data.experience_id,
        )
        if experience is None:
            raise EntityNotFoundError(data.experience_id)
        if experience.user_id != data.actor_id:
            raise NotResourceOwnerError(data.experience_id, data.actor_id)
        previous_file_id = experience.remove_icon()
        if previous_file_id is not None:
            previous_file = await self._files_gateway.with_id(
                previous_file_id,
            )
            if previous_file is not None and not previous_file.is_deleted:
                previous_file.mark_deleted()
        await self._transaction.commit()
