from dataclasses import dataclass
from typing import Protocol

from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.models import UserID
from learnic.entities.user_social_link.models import UserSocialLink


@dataclass(slots=True, frozen=True)
class UserSocialLinkView:
    """Read-side projection of :class:`UserSocialLink`.

    The view leaves ``kind`` as the raw enum value (string) so the
    HTTP layer can pass it straight through without re-translating.
    """

    kind: SocialLinkKind
    url: str
    position: int


class UserSocialLinkGateway(Protocol):
    """Write-side lookups for :class:`UserSocialLink`."""

    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserSocialLink]: ...

    async def delete_for_user(self, user_id: UserID) -> None:
        """Remove every social-link row owned by the user.

        Used by the PUT-list command before re-inserting the supplied
        rows so the persisted set always equals what the SPA sent.
        """
        ...


class UserSocialLinkReader(Protocol):
    """Read-side queries returning :class:`UserSocialLinkView` projections."""

    async def for_user(
        self,
        user_id: UserID,
    ) -> list[UserSocialLinkView]: ...
