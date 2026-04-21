from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.entities.user.models import User, UserID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    Patronymic,
)


@dataclass(slots=True, frozen=True)
class CreateUserCommand:
    email: str
    first_name: str
    last_name: str
    patronymic: str | None = None


@final
class CreateUserCommandHandler:
    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver

    async def run(self, data: CreateUserCommand) -> UserID:
        user = User.create_user(
            email=Email(data.email),
            first_name=FirstName(data.first_name),
            last_name=LastName(data.last_name),
            patronymic=(
                Patronymic(data.patronymic)
                if data.patronymic is not None
                else None
            ),
        )
        self._entity_saver.add_one(user)
        await self._transaction.commit()
        return user.oid
