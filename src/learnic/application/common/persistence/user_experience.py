from dataclasses import dataclass
from datetime import date
from typing import Protocol

from learnic.application.common.persistence.file import FileMeta
from learnic.entities.user.models import UserID
from learnic.entities.user_experience.ids import UserExperienceID
from learnic.entities.user_experience.models import UserExperience


@dataclass(slots=True, frozen=True)
class UserExperienceView:
    """Read-side projection of :class:`UserExperience`.

    ``icon`` carries enough storage metadata for the application
    layer to resolve a presigned URL without a second round-trip;
    ``None`` means the entry has no icon attached.
    """

    oid: UserExperienceID
    user_id: UserID
    title: str
    description: str | None
    start_date: date
    end_date: date | None
    source_url: str | None
    icon: FileMeta | None


class UserExperienceGateway(Protocol):
    """Write-side lookups for :class:`UserExperience`."""

    async def with_id(
        self,
        oid: UserExperienceID,
    ) -> UserExperience | None: ...

    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserExperience]: ...

    async def delete(self, experience: UserExperience) -> None: ...


class UserExperienceReader(Protocol):
    """Read-side queries returning :class:`UserExperienceView` projections."""

    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserExperienceView]: ...

    async def count_for_user(self, user_id: UserID) -> int:
        """Return how many experience entries ``user_id`` has."""
        ...
