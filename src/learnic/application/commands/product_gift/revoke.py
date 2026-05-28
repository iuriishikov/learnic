from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    GiftRevokedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RevokeGiftCommand:
    actor_id: UserID
    gift_id: ProductGiftID


@final
class RevokeGiftCommandHandler:
    """Cancel a still-pending gift.

    Caller must hold ``MANAGE_RELEASES`` on the product — same gate as
    issuing the gift. Only a ``PENDING_INVITE`` gift can be revoked
    (the entity enforces this); an accepted gift already produced an
    enrollment and is not undone here. If the recipient is a
    registered user their card is republished so it flips to revoked.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        gift_gateway: ProductGiftGateway,
        notifications: NotificationPublisher,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._gift_gateway: Final = gift_gateway
        self._notifications: Final = notifications
        self._event_bus: Final = event_bus

    async def run(self, data: RevokeGiftCommand) -> None:
        gift = await self._gift_gateway.with_id(data.gift_id)
        if gift is None:
            raise EntityNotFoundError(data.gift_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(gift.product_id),
            Permission.MANAGE_RELEASES,
        )
        recipient_id = gift.recipient_id
        gift.revoke()
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=GiftRevokedPayload.of(gift.oid),
            product_id=gift.product_id,
            actor_id=data.actor_id,
        )
        if recipient_id is not None:
            await self._notifications.republish_for_gift(
                recipient_id=recipient_id,
                gift_id=gift.oid,
            )
