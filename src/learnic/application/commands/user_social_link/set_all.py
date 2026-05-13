from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.persistence.user_social_link import (
    UserSocialLinkGateway,
)
from learnic.entities.user.constants import SOCIAL_LINKS_MAX_COUNT
from learnic.entities.user.enums import SocialLinkKind
from learnic.entities.user.errors import TooManySocialLinksError
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import SocialLinkUrl
from learnic.entities.user_social_link.models import UserSocialLink


@dataclass(slots=True, frozen=True)
class SocialLinkInput:
    kind: SocialLinkKind
    url: str


@dataclass(slots=True, frozen=True)
class SetUserSocialLinksCommand:
    """PUT-list payload: replace every row owned by ``user_id``.

    The order of ``items`` becomes the persisted ``position`` so the
    SPA can reorder by sending the list in a new order.
    """

    user_id: UserID
    items: tuple[SocialLinkInput, ...]


@final
class SetUserSocialLinksCommandHandler:
    """Wipe-and-replace handler for the user's social-link list.

    Cheaper than diffing for a list capped at
    :data:`SOCIAL_LINKS_MAX_COUNT` rows, and the public profile
    cares only about the final state — there are no per-row
    events to preserve.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        user_gateway: UserGateway,
        social_link_gateway: UserSocialLinkGateway,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._user_gateway: Final = user_gateway
        self._social_link_gateway: Final = social_link_gateway

    async def run(self, data: SetUserSocialLinksCommand) -> None:
        if len(data.items) > SOCIAL_LINKS_MAX_COUNT:
            raise TooManySocialLinksError(SOCIAL_LINKS_MAX_COUNT)
        user = await self._user_gateway.with_id(data.user_id)
        if user is None:
            raise EntityNotFoundError(data.user_id)
        # VO instantiation validates URL invariants *before* we touch
        # the database — keeps "all-or-nothing" semantics when one of
        # the supplied URLs is malformed.
        prepared: list[UserSocialLink] = []
        for index, raw in enumerate(data.items):
            prepared.append(
                UserSocialLink.create(
                    user_id=data.user_id,
                    kind=raw.kind,
                    url=SocialLinkUrl(raw.url),
                    position=index,
                ),
            )
        await self._social_link_gateway.delete_for_user(data.user_id)
        await self._transaction.flush()
        for link in prepared:
            self._entity_saver.add_one(link)
        await self._transaction.commit()
