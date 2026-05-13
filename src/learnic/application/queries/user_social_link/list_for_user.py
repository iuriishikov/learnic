from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.user_social_link import (
    UserSocialLinkReader,
    UserSocialLinkView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListUserSocialLinksQuery:
    user_id: UserID


@final
class ListUserSocialLinksQueryHandler:
    """Returns the user's social-link list, ordered by position."""

    def __init__(self, reader: UserSocialLinkReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: ListUserSocialLinksQuery,
    ) -> list[UserSocialLinkView]:
        return await self._reader.for_user(data.user_id)
