import uuid
from dataclasses import dataclass
from typing import NewType, Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    Patronymic,
)

UserID = NewType("UserID", uuid.UUID)


@dataclass
class User(BaseEntity[UserID]):
    email: Email
    first_name: FirstName
    last_name: LastName
    patronymic: Patronymic | None

    def change_email(self, new_email: Email) -> None:
        self.email = new_email

    def change_first_name(self, new_first_name: FirstName) -> None:
        self.first_name = new_first_name

    def change_last_name(self, new_last_name: LastName) -> None:
        self.last_name = new_last_name

    def change_patronymic(self, new_patronymic: Patronymic | None) -> None:
        self.patronymic = new_patronymic

    @classmethod
    def create_user(
        cls,
        email: Email,
        first_name: FirstName,
        last_name: LastName,
        patronymic: Patronymic | None = None,
    ) -> Self:
        return cls(
            oid=UserID(uuid.uuid4()),
            email=email,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
        )
