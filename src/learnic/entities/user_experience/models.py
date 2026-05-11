import uuid
from dataclasses import dataclass
from datetime import date
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.errors import (
    InvalidExperienceDateRangeError,
)
from learnic.entities.user_experience.ids import UserExperienceID
from learnic.entities.user_experience.value_objects import (
    ExperienceDescription,
    ExperienceSourceUrl,
    ExperienceTitle,
)


@dataclass
class UserExperience(BaseEntity[UserExperienceID]):
    """A single work / study entry attached to a :class:`User`.

    Owned by a user (CASCADE on parent delete), exposed through its
    own Gateway/Reader so individual rows can be edited and ordered
    without rehydrating the user.

    ``end_date is None`` encodes an ongoing experience ("Jan 2018 –
    Present") — the only date invariant is that, when both endpoints
    are set, the end does not precede the start.
    """

    user_id: UserID
    title: ExperienceTitle
    description: ExperienceDescription | None
    start_date: date
    end_date: date | None
    source_url: ExperienceSourceUrl | None
    icon_file_id: FileID | None

    def change_title(self, new_title: ExperienceTitle) -> None:
        self.title = new_title

    def change_description(
        self,
        new_description: ExperienceDescription | None,
    ) -> None:
        self.description = new_description

    def change_dates(
        self,
        new_start_date: date,
        new_end_date: date | None,
    ) -> None:
        _validate_date_range(new_start_date, new_end_date)
        self.start_date = new_start_date
        self.end_date = new_end_date

    def change_source_url(
        self,
        new_source_url: ExperienceSourceUrl | None,
    ) -> None:
        self.source_url = new_source_url

    def set_icon(self, file_id: FileID) -> FileID | None:
        """Attach ``file_id`` as icon, returning the previous one (if any)."""
        previous = self.icon_file_id
        self.icon_file_id = file_id
        return previous

    def remove_icon(self) -> FileID | None:
        previous = self.icon_file_id
        self.icon_file_id = None
        return previous

    @classmethod
    def create(
        cls,
        user_id: UserID,
        title: ExperienceTitle,
        start_date: date,
        end_date: date | None = None,
        description: ExperienceDescription | None = None,
        source_url: ExperienceSourceUrl | None = None,
        icon_file_id: FileID | None = None,
    ) -> Self:
        _validate_date_range(start_date, end_date)
        return cls(
            oid=UserExperienceID(uuid.uuid4()),
            user_id=user_id,
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            source_url=source_url,
            icon_file_id=icon_file_id,
        )


def _validate_date_range(start: date, end: date | None) -> None:
    if end is not None and end < start:
        raise InvalidExperienceDateRangeError
