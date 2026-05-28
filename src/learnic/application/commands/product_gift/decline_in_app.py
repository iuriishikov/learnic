from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    GiftDeclinedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.commands.product_gift._identity import (
    ensure_addressee,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeclineGiftCommand:
    actor_id: UserID
    gift_id: ProductGiftID


@final
class DeclineGiftCommandHandler:
    """Decline a pending gift (in-app card or email link).

    Same addressee gate as the accept handlers, but flips the gift to
    ``DECLINED`` and notifies the gifter. No enrollment is created.
    """

    def __init__(
        self,
        transaction: Transaction,
        gift_gateway: ProductGiftGateway,
        user_gateway: UserGateway,
        notifications: NotificationPublisher,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._gift_gateway: Final = gift_gateway
        self._user_gateway: Final = user_gateway
        self._notifications: Final = notifications
        self._event_bus: Final = event_bus

    async def run(self, data: DeclineGiftCommand) -> None:
        gift = await self._gift_gateway.with_id(data.gift_id)
        if gift is None:
            raise EntityNotFoundError(data.gift_id)
        actor = await self._user_gateway.with_id(data.actor_id)
        if actor is None:
            raise EntityNotFoundError(data.actor_id)
        ensure_addressee(gift, actor, data.actor_id)
        gift.decline_in_app(data.actor_id)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=GiftDeclinedPayload.of(gift.oid),
            product_id=gift.product_id,
            actor_id=data.actor_id,
        )
        await self._notifications.republish_for_gift(
            recipient_id=data.actor_id,
            gift_id=gift.oid,
        )
        await self._notifications.publish(
            Notification.for_gift_declined(
                recipient_id=gift.invited_by,
                actor_id=data.actor_id,
                gift_id=gift.oid,
                product_id=gift.product_id,
                decliner_id=data.actor_id,
            ),
        )
