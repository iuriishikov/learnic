from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.persistence.product_gift import (
    ProductGiftReader,
    ProductGiftView,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetGiftQuery:
    actor_id: UserID
    gift_id: ProductGiftID


@final
class GetGiftQueryHandler:
    """Load a single gift for the email-link landing page.

    Authorised to the addressee or the gifter only: the recipient
    (by id), the invited email's owner, or the user who issued the
    gift. Anyone else gets ``403`` so a guessed gift id does not leak
    the recipient's email / product. A missing gift is ``404``.
    """

    def __init__(
        self,
        reader: ProductGiftReader,
        user_gateway: UserGateway,
    ) -> None:
        self._reader: Final = reader
        self._user_gateway: Final = user_gateway

    async def run(self, data: GetGiftQuery) -> ProductGiftView:
        view = await self._reader.with_id(data.gift_id)
        if view is None:
            raise EntityNotFoundError(data.gift_id)
        if await self._is_allowed(view, data.actor_id):
            return view
        raise NotResourceOwnerError(data.gift_id, data.actor_id)

    async def _is_allowed(
        self,
        view: ProductGiftView,
        actor_id: UserID,
    ) -> bool:
        if view.gifter.oid == actor_id:
            return True
        if view.recipient is not None and view.recipient.oid == actor_id:
            return True
        if view.invited_email is None:
            return False
        actor = await self._user_gateway.with_id(actor_id)
        return actor is not None and actor.email.value == view.invited_email
