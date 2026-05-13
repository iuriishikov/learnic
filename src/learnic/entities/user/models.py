import uuid
from dataclasses import dataclass
from typing import NewType, Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID
from learnic.entities.user.value_objects import (
    Email,
    FirstName,
    LastName,
    PasswordHash,
    Patronymic,
    PortfolioUrl,
    PublicEmail,
    UserDescription,
    WebsiteUrl,
)

UserID = NewType("UserID", uuid.UUID)


@dataclass
class User(BaseEntity[UserID]):
    email: Email
    first_name: FirstName
    last_name: LastName
    patronymic: Patronymic | None
    password_hash: PasswordHash
    email_verified: bool
    is_verified: bool = False
    description: UserDescription | None = None
    avatar_file_id: FileID | None = None
    cover_file_id: FileID | None = None
    website_url: WebsiteUrl | None = None
    portfolio_url: PortfolioUrl | None = None
    public_email: PublicEmail | None = None

    def change_email(self, new_email: Email) -> None:
        self.email = new_email
        self.email_verified = False

    def change_first_name(self, new_first_name: FirstName) -> None:
        self.first_name = new_first_name

    def change_last_name(self, new_last_name: LastName) -> None:
        self.last_name = new_last_name

    def change_patronymic(self, new_patronymic: Patronymic | None) -> None:
        self.patronymic = new_patronymic

    def change_password(self, new_hash: PasswordHash) -> None:
        self.password_hash = new_hash

    def change_description(self, new_description: UserDescription | None) -> None:
        self.description = new_description

    def mark_email_verified(self) -> None:
        self.email_verified = True

    def set_avatar(self, file_id: FileID) -> FileID | None:
        """Attach ``file_id`` as avatar, returning the previous one (if any)."""
        previous = self.avatar_file_id
        self.avatar_file_id = file_id
        return previous

    def remove_avatar(self) -> FileID | None:
        previous = self.avatar_file_id
        self.avatar_file_id = None
        return previous

    def set_cover(self, file_id: FileID) -> FileID | None:
        previous = self.cover_file_id
        self.cover_file_id = file_id
        return previous

    def remove_cover(self) -> FileID | None:
        previous = self.cover_file_id
        self.cover_file_id = None
        return previous

    def change_website_url(self, new_value: WebsiteUrl | None) -> None:
        self.website_url = new_value

    def change_portfolio_url(self, new_value: PortfolioUrl | None) -> None:
        self.portfolio_url = new_value

    def change_public_email(self, new_value: PublicEmail | None) -> None:
        self.public_email = new_value

    @classmethod
    def create_user(
        cls,
        email: Email,
        first_name: FirstName,
        last_name: LastName,
        password_hash: PasswordHash,
        patronymic: Patronymic | None = None,
    ) -> Self:
        return cls(
            oid=UserID(uuid.uuid4()),
            email=email,
            first_name=first_name,
            last_name=last_name,
            patronymic=patronymic,
            password_hash=password_hash,
            email_verified=False,
            is_verified=False,
            description=None,
            avatar_file_id=None,
            cover_file_id=None,
        )
