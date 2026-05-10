from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    make_collaboration_payload,
    publish_product_event,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.product.ids import ProductID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class LeaveProductCommand:
    actor_id: UserID
    product_id: ProductID


@final
class LeaveProductCommandHandler:
    """Self-revoke from a product collaboration.

    Same effect as :class:`RevokeCollaborationCommandHandler`, but
    initiated by the collaborator themselves and not authorized
    against ``MANAGE_COLLABORATORS`` — leaving is always allowed.
    The product author gets an email notification so they're aware
    a collaborator stepped away.
    """

    def __init__(
        self,
        transaction: Transaction,
        product_gateway: ProductGateway,
        collab_gateway: ProductCollaborationGateway,
        user_gateway: UserGateway,
        scheduler: TaskScheduler,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._product_gateway: Final = product_gateway
        self._collab_gateway: Final = collab_gateway
        self._user_gateway: Final = user_gateway
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications

    async def run(self, data: LeaveProductCommand) -> None:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id == data.actor_id:
            # Author leaves their own product? meaningless — refuse.
            raise NotResourceOwnerError(data.product_id, data.actor_id)
        collab = await self._collab_gateway.active_for_product_and_user(
            data.product_id,
            data.actor_id,
        )
        if collab is None:
            raise EntityNotFoundError(data.product_id)
        collab.revoke()
        await self._transaction.commit()
        owner = await self._user_gateway.with_id(product.author_id)
        if owner is not None:
            await self._scheduler.schedule_send_collaboration_left_email(
                to=owner.email.value,
                product_id=data.product_id,
                collaborator_id=data.actor_id,
            )
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.COLLABORATION_REVOKED,
            product_id=data.product_id,
            actor_id=data.actor_id,
            payload=make_collaboration_payload(
                collaboration_id=collab.oid,
                collaborator_id=data.actor_id,
            ),
        )
        # The leaver's own ``invite_sent`` card (now in ACTIVE state
        # since they accepted earlier) needs to flip to REVOKED in
        # real time so their panel does not keep an "active" indicator
        # for a collaboration they just walked away from.
        await self._notifications.republish_for_collaboration(
            recipient_id=data.actor_id,
            collaboration_id=collab.oid,
        )
