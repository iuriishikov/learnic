from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    CollaborationRevokedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
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
        notifier: Notifier,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
        security: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._product_gateway: Final = product_gateway
        self._collab_gateway: Final = collab_gateway
        self._notifier: Final = notifier
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications
        self._security: Final = security

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
        base = self._security.frontend_base_url.rstrip("/")
        link = f"{base}/products/{data.product_id}"
        await self._notifier.send(
            recipient_id=product.author_id,
            category=NotificationCategory.TEACHING,
            payloads={
                NotificationChannel.EMAIL: EmailPayload(
                    subject="Коллаборатор покинул продукт",
                    components=[
                        EmailParagraph.text("Здравствуйте!"),
                        EmailParagraph.text(
                            "Один из коллабораторов покинул ваш продукт.",
                        ),
                        EmailButton(label="Открыть продукт", url=link),
                    ],
                ),
            },
        )
        await publish_product_event(
            self._event_bus,
            payload=CollaborationRevokedPayload.of(
                collaboration_id=collab.oid,
                collaborator_id=data.actor_id,
            ),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        # The leaver's own ``invite_sent`` card (now in ACTIVE state
        # since they accepted earlier) needs to flip to REVOKED in
        # real time so their panel does not keep an "active" indicator
        # for a collaboration they just walked away from.
        await self._notifications.republish_for_collaboration(
            recipient_id=data.actor_id,
            collaboration_id=collab.oid,
        )
