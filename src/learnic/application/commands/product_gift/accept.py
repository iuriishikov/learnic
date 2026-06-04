from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.enrollment.service import EnrollmentService
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import ProductEventBus
from learnic.application.commands.product_gift._acceptance import (
    check_product_enrollable,
    finalize_acceptance,
)
from learnic.application.commands.product_gift._identity import (
    ensure_addressee,
)
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.value_objects import InviteToken
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AcceptGiftByTokenCommand:
    actor_id: UserID
    gift_id: ProductGiftID
    raw_token: str


@final
class AcceptGiftByTokenCommandHandler:
    """Accept a gift via the email link (token-validated).

    Used by the SPA landing route ``/gifts/{id}/accept`` which carries
    the plaintext token from the email. Validates addressee + token +
    TTL, creates the note enrollment, and notifies the gifter.
    """

    def __init__(
        self,
        transaction: Transaction,
        gift_gateway: ProductGiftGateway,
        user_gateway: UserGateway,
        product_gateway: ProductGateway,
        enrollment_service: EnrollmentService,
        notifications: NotificationPublisher,
        event_bus: ProductEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._gift_gateway: Final = gift_gateway
        self._user_gateway: Final = user_gateway
        self._product_gateway: Final = product_gateway
        self._enrollment_service: Final = enrollment_service
        self._notifications: Final = notifications
        self._event_bus: Final = event_bus

    async def run(self, data: AcceptGiftByTokenCommand) -> None:
        gift = await self._gift_gateway.with_id(data.gift_id)
        if gift is None:
            raise EntityNotFoundError(data.gift_id)
        actor = await self._user_gateway.with_id(data.actor_id)
        if actor is None:
            raise EntityNotFoundError(data.actor_id)
        ensure_addressee(gift, actor, data.actor_id)
        await check_product_enrollable(gift, self._product_gateway)
        gift.accept(data.actor_id, InviteToken(data.raw_token))
        await finalize_acceptance(
            gift=gift,
            actor_id=data.actor_id,
            enrollment_service=self._enrollment_service,
            transaction=self._transaction,
            notifications=self._notifications,
            event_bus=self._event_bus,
        )
