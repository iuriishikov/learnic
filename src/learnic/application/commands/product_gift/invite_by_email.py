from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.email.rate_limit import (
    EmailSendRateLimiter,
)
from learnic.application.common.errors import (
    CannotEnrollInUnpublishedProductError,
    CannotGiftToOwnerError,
    EmailInviteRateLimitExceededError,
    EntityNotFoundError,
    GiftAlreadyExistsError,
    ProductNotGiftableError,
)
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
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.application.commands.product_gift._email import (
    GIFT_EMAIL_SUBJECT,
    build_gift_email_components,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.product_gift.value_objects import InviteToken
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import Email

MAX_EMAIL_GIFTS_PER_DAY: Final = 10
EMAIL_GIFT_RATE_LIMIT_WINDOW: Final = timedelta(days=1)


@dataclass(slots=True, frozen=True)
class InviteGiftByEmailCommand:
    actor_id: UserID
    product_id: ProductID
    target_email: str
    actor_ip: str | None


@final
class InviteGiftByEmailCommandHandler:
    """Gift product access to a (possibly unregistered) email address.

    Mirrors :class:`InviteGiftByUserCommandHandler`, but the target
    need not have an account yet — the email's Accept / Decline
    buttons land them on the SPA which bounces through login /
    register and back. If the email belongs to a registered user who
    already has a live gift, the handler refuses with
    :class:`GiftAlreadyExistsError`. Registered targets also get the
    in-app card + push; unregistered ones only get the email until
    they sign up and accept.

    A per-actor daily cap shields the upstream email provider's quota
    from a compromised account flooding gifts to arbitrary addresses.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        authorizer: Authorizer,
        product_gateway: ProductGateway,
        user_gateway: UserGateway,
        gift_gateway: ProductGiftGateway,
        scheduler: TaskScheduler,
        notifications: NotificationPublisher,
        event_bus: ProductEventBus,
        security: SecurityPolicies,
        email_rate_limiter: EmailSendRateLimiter,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._authorizer: Final = authorizer
        self._product_gateway: Final = product_gateway
        self._user_gateway: Final = user_gateway
        self._gift_gateway: Final = gift_gateway
        self._scheduler: Final = scheduler
        self._notifications: Final = notifications
        self._event_bus: Final = event_bus
        self._security: Final = security
        self._email_rate_limiter: Final = email_rate_limiter

    async def run(
        self,
        data: InviteGiftByEmailCommand,
    ) -> ProductGiftID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.type is not ProductType.NOTE:
            raise ProductNotGiftableError(
                data.product_id,
                product.type.value,
            )
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
        email = Email(data.target_email)
        existing_user = await self._user_gateway.with_email(email.value)
        if existing_user is not None:
            if existing_user.oid == product.author_id:
                raise CannotGiftToOwnerError(
                    data.product_id,
                    existing_user.oid,
                )
            existing = await self._gift_gateway.active_for_product_and_user(
                data.product_id,
                existing_user.oid,
            )
            if existing is not None:
                raise GiftAlreadyExistsError(
                    product_id=data.product_id,
                    recipient_id=existing_user.oid,
                )
        pending = await self._gift_gateway.pending_for_product_and_email(
            data.product_id,
            email.value,
        )
        if pending is not None:
            raise GiftAlreadyExistsError(
                product_id=data.product_id,
                invited_email=email.value,
            )
        since = datetime.now(timezone.utc) - EMAIL_GIFT_RATE_LIMIT_WINDOW
        recent = await self._gift_gateway.count_email_invites_by_actor_since(
            data.actor_id,
            since,
        )
        if recent >= MAX_EMAIL_GIFTS_PER_DAY:
            raise EmailInviteRateLimitExceededError(
                actor_id=data.actor_id,
                limit=MAX_EMAIL_GIFTS_PER_DAY,
                retry_after_seconds=int(
                    EMAIL_GIFT_RATE_LIMIT_WINDOW.total_seconds(),
                ),
            )
        token = InviteToken.generate()
        gift = ProductGift.invite_by_email(
            product_id=data.product_id,
            invited_email=email,
            invited_by=data.actor_id,
            token=token,
        )
        self._entity_saver.add_one(gift)
        await self._email_rate_limiter.register(
            actor_id=data.actor_id,
            recipient=email.value,
            ip=data.actor_ip,
        )
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=GiftIssuedPayload.of(gift.oid),
            product_id=data.product_id,
            actor_id=data.actor_id,
        )
        await self._scheduler.schedule_send_email(
            to=email.value,
            subject=GIFT_EMAIL_SUBJECT,
            components=build_gift_email_components(
                frontend_base_url=self._security.frontend_base_url,
                gift_id=gift.oid,
                token=token,
                product_name=product.name.value,
            ),
        )
        if existing_user is not None:
            await self._notifications.publish(
                Notification.for_gift_received(
                    recipient_id=existing_user.oid,
                    actor_id=data.actor_id,
                    gift_id=gift.oid,
                    product_id=data.product_id,
                ),
            )
        return gift.oid
