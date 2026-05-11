from dataclasses import dataclass
from datetime import date
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.ids import UserExperienceID
from learnic.entities.user_experience.models import UserExperience
from learnic.entities.user_experience.value_objects import (
    ExperienceDescription,
    ExperienceSourceUrl,
    ExperienceTitle,
)


@dataclass(slots=True, frozen=True)
class AddUserExperienceCommand:
    user_id: UserID
    title: str
    start_date: date
    end_date: date | None
    description: str | None
    source_url: str | None


@final
class AddUserExperienceCommandHandler:
    """Adds a new experience entry to the acting user.

    The icon is uploaded through the dedicated
    ``SetUserExperienceIconCommandHandler`` after creation — keeps
    the create payload JSON-only and mirrors the avatar / cover
    handling on :class:`User`.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        user_gateway: UserGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway

    async def run(
        self,
        data: AddUserExperienceCommand,
    ) -> UserExperienceID:
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        experience = UserExperience.create(
            user_id=data.user_id,
            title=ExperienceTitle(data.title),
            start_date=data.start_date,
            end_date=data.end_date,
            description=(
                ExperienceDescription(data.description)
                if data.description is not None
                else None
            ),
            source_url=(
                ExperienceSourceUrl(data.source_url)
                if data.source_url is not None
                else None
            ),
        )
        self._entity_saver.add_one(experience)
        await self._transaction.commit()
        return experience.oid
