from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.resource_lineage import (
    ResourceLineageReader,
)
from learnic.application.common.auth.role_hierarchy import RoleHierarchy
from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.errors import (
    CannotInviteOwnerError,
    CollaborationAlreadyExistsError,
    EntityNotFoundError,
)
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product import ProductGateway
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
    ProductCollaborationSaver,
)
from learnic.application.common.persistence.role import RoleGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    ProductEventBus,
    ProductEventKind,
    make_collaboration_payload,
    publish_product_event,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.commands.product_collaboration._grant_spec import (
    GrantSpec,
    GrantSpecResolver,
)
from learnic.entities.notification.enums import (
    NotificationCategory,
    NotificationChannel,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_TTL_DAYS,
)
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.product_collaboration.value_objects import InviteToken
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class InviteCollaboratorByUserCommand:
    actor_id: UserID
    product_id: ProductID
    target_user_id: UserID
    grants: list[GrantSpec]


@final
class InviteCollaboratorByUserCommandHandler:
    """Invite an already-registered user to collaborate on a product.

    Caller must hold ``MANAGE_COLLABORATORS`` (typically only the
    owner or a collaborator with a custom role granting that
    permission). The target must be a registered user
    (the email path is :class:`InviteCollaboratorByEmailCommandHandler`),
    must not be the product author, and must not already have an
    active or pending invite for the same product. A fresh
    :class:`InviteToken` is generated, hashed into the row, and the
    plaintext is enqueued for delivery via TaskIQ.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        hierarchy: RoleHierarchy,
        product_gateway: ProductGateway,
        user_gateway: UserGateway,
        collab_gateway: ProductCollaborationGateway,
        collab_saver: ProductCollaborationSaver,
        role_gateway: RoleGateway,
        lineage: ResourceLineageReader,
        notifier: Notifier,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
        security: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy
        self._product_gateway: Final = product_gateway
        self._user_gateway: Final = user_gateway
        self._collab_gateway: Final = collab_gateway
        self._collab_saver: Final = collab_saver
        self._resolver: Final = GrantSpecResolver(role_gateway, lineage)
        self._notifier: Final = notifier
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications
        self._security: Final = security

    async def run(
        self,
        data: InviteCollaboratorByUserCommand,
    ) -> ProductCollaborationID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
        if product.author_id == data.target_user_id:
            raise CannotInviteOwnerError(
                data.product_id,
                data.target_user_id,
            )
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_COLLABORATORS,
        )
        await self._hierarchy.require_can_assign_roles(
            data.product_id,
            data.actor_id,
            [spec.role_id for spec in data.grants],
        )
        target = await self._user_gateway.with_id(data.target_user_id)
        if target is None:
            raise EntityNotFoundError(data.target_user_id)
        existing = await self._collab_gateway.active_for_product_and_user(
            data.product_id,
            data.target_user_id,
        )
        if existing is not None:
            raise CollaborationAlreadyExistsError(
                product_id=data.product_id,
                collaborator_id=data.target_user_id,
            )
        grants = await self._resolver.resolve(
            data.product_id,
            data.grants,
        )
        token = InviteToken.generate()
        collab = ProductCollaboration.invite_existing_user(
            product_id=data.product_id,
            collaborator_id=data.target_user_id,
            invited_by=data.actor_id,
            grants=grants,
            token=token,
        )
        await self._collab_saver.save(collab)
        await self._transaction.commit()
        base = self._security.frontend_base_url.rstrip("/")
        link = (
            f"{base}/products/{data.product_id}"
            f"/collaboration-invitation/{collab.oid}"
            f"/accept?token={token.value}"
        )
        await self._notifier.send(
            recipient_id=data.target_user_id,
            category=NotificationCategory.TEACHING,
            payloads={
                NotificationChannel.EMAIL: EmailPayload(
                    subject="Приглашение к совместной работе на Learnic",
                    components=[
                        EmailParagraph.text("Здравствуйте!"),
                        EmailParagraph.text(
                            "Вас пригласили в совместную работу над продуктом "
                            "на платформе Learnic.",
                        ),
                        EmailButton(label="Принять приглашение", url=link),
                        EmailParagraph.text(
                            f"Ссылка действует {INVITE_TOKEN_TTL_DAYS} дней. "
                            "После того как вы примете приглашение, нужные "
                            "права будут выданы автоматически.",
                        ),
                    ],
                ),
            },
        )
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.COLLABORATION_INVITED,
            product_id=data.product_id,
            actor_id=data.actor_id,
            payload=make_collaboration_payload(
                collaboration_id=collab.oid,
                collaborator_id=data.target_user_id,
            ),
        )
        await self._notifications.publish(
            Notification.for_invite_sent(
                recipient_id=data.target_user_id,
                actor_id=data.actor_id,
                collaboration_id=collab.oid,
                product_id=data.product_id,
            ),
        )
        return collab.oid
