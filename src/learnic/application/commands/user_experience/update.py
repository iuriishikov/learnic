from dataclasses import dataclass
from datetime import date
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user_experience import (
    UserExperienceGateway,
)
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.ids import UserExperienceID
from learnic.entities.user_experience.value_objects import (
    ExperienceDescription,
    ExperienceSourceUrl,
    ExperienceTitle,
)


@dataclass(slots=True, frozen=True)
class UpdateUserExperienceCommand:
    """PUT-style replace of every editable field on an experience.

    ``description`` / ``source_url`` / ``end_date`` accept ``None``
    to clear the field; ``title`` and ``start_date`` are required.
    The icon is managed through its own command pair, so it is
    intentionally absent here.
    """

    actor_id: UserID
    experience_id: UserExperienceID
    title: str
    start_date: date
    end_date: date | None
    description: str | None
    source_url: str | None


@final
class UpdateUserExperienceCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        experience_gateway: UserExperienceGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._experience_gateway: Final = experience_gateway

    async def run(self, data: UpdateUserExperienceCommand) -> None:
        experience = await self._experience_gateway.with_id(
            data.experience_id,
        )
        if experience is None:
            raise EntityNotFoundError(data.experience_id)
        if experience.user_id != data.actor_id:
            raise NotResourceOwnerError(data.experience_id, data.actor_id)
        experience.change_title(ExperienceTitle(data.title))
        experience.change_dates(data.start_date, data.end_date)
        experience.change_description(
            ExperienceDescription(data.description)
            if data.description is not None
            else None,
        )
        experience.change_source_url(
            ExperienceSourceUrl(data.source_url)
            if data.source_url is not None
            else None,
        )
        await self._transaction.commit()
