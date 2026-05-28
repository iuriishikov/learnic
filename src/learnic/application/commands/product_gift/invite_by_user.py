from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.errors import (
    CannotEnrollInUnpublishedProductError,
    CannotGiftToOwnerError,
    EntityNotFoundError,
    GiftAlreadyExistsError,
    ProductNotGiftableError,
)
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_gift import (
    ProductGiftGateway,
)
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    GiftIssuedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.commands.product_gift._email import (
    GIFT_EMAIL_SUBJECT,
    build_gift_email_components,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.product_gift.value_objects import InviteToken
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class InviteGiftByUserCommand:
    actor_id: UserID
    product_id: ProductID
    recipient_id: UserID


@final
class InviteGiftByUserCommandHandler:
    """Gift product access to an already-registered user.

    Caller must hold ``MANAGE_RELEASES`` on the product (the same
    permission family that governs granting student access). The
    product must be a ``COURSE`` and ``PUBLISHED``, the recipient
    must not be the author, and there must be no existing pending /
    accepted gift for the same ``(product, user)`` pair. A fresh
    :class:`InviteToken` is generated; the recipient receives an
    email with Accept / Decline buttons plus an in-app card and a
    push banner. The enrollment is only created when the recipient
    accepts.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        user_gateway: UserGateway,
        gift_gateway: ProductGiftGateway,
        notifier: Notifier,
        notifications: NotificationPublisher,
        event_bus: ProductEventBus,
        security: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._user_gateway: Final = user_gateway
        self._gift_gateway: Final = gift_gateway
        self._notifier: Final = notifier
        self._notifications: Final = notifications
        self._event_bus: Final = event_bus
        self._security: Final = security

    async def run(
        self,
        data: InviteGiftByUserCommand,
    ) -> ProductGiftID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.type is not ProductType.COURSE:
            raise ProductNotGiftableError(
                data.product_id,
                product.type.value,
            )
        if product.author_id == data.recipient_id:
            raise CannotGiftToOwnerError(data.product_id, data.recipient_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_RELEASES,
        )
        if product.status is not ProductStatus.PUBLISHED:
            raise CannotEnrollInUnpublishedProductError(
                product_id=product.oid,
                status=product.status.value,
            )
        recipient = await self._user_gateway.with_id(data.recipient_id)
        if recipient is None:
            raise EntityNotFoundError(data.recipient_id)
        existing = await self._gift_gateway.active_for_product_and_user(
            data.product_id,
            data.recipient_id,
        )
        if existing is not None:
            raise GiftAlreadyExistsError(
                product_id=data.product_id,
                recipient_id=data.recipient_id,
            )
        token = InviteToken.generate()
        gift = ProductGift.invite_existing_user(
            product_id=data.product_id,
            recipient_id=data.recipient_id,
            invited_by=data.actor_id,
            token=token,
        )
        self._entity_saver.add_one(gift)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=GiftIssuedPayload.of(gift.oid),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        await self._notifier.send(
            recipient_id=data.recipient_id,
            category=NotificationCategory.LEARNING,
            payloads={
                NotificationChannel.EMAIL: EmailPayload(
                    subject=GIFT_EMAIL_SUBJECT,
                    components=build_gift_email_components(
                        frontend_base_url=self._security.frontend_base_url,
                        gift_id=gift.oid,
                        token=token,
                        product_name=product.name.value,
                    ),
                ),
            },
        )
        await self._notifications.publish(
            Notification.for_gift_received(
                recipient_id=data.recipient_id,
                actor_id=data.actor_id,
                gift_id=gift.oid,
                product_id=data.product_id,
            ),
        )
        return gift.oid
