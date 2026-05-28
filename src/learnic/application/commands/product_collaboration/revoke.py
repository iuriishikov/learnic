from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.role_hierarchy import RoleHierarchy
from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.email.rate_limit import (
    EmailSendRateLimiter,
)
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    CollaborationRevokedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.entities.notification.models import Notification
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class RevokeCollaborationCommand:
    actor_id: UserID
    collaboration_id: ProductCollaborationID
    actor_ip: str | None


@final
class RevokeCollaborationCommandHandler:
    """Revoke a collaboration (active or pending).

    Status flips to ``REVOKED`` and the row is preserved for audit.
    The revoked collaborator (if known) gets an email notification.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        hierarchy: RoleHierarchy,
        collab_gateway: ProductCollaborationGateway,
        user_gateway: UserGateway,
        scheduler: TaskScheduler,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
        security: SecurityPolicies,
        email_rate_limiter: EmailSendRateLimiter,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy
        self._collab_gateway: Final = collab_gateway
        self._user_gateway: Final = user_gateway
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications
        self._security: Final = security
        self._email_rate_limiter: Final = email_rate_limiter

    async def run(
        self,
        data: RevokeCollaborationCommand,
    ) -> None:
        collab = await self._collab_gateway.with_id(data.collaboration_id)
        if collab is None:
            raise EntityNotFoundError(data.collaboration_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(collab.product_id),
            Permission.MANAGE_COLLABORATORS,
        )
        if collab.collaborator_id is not None:
            await self._hierarchy.require_can_act_on_user(
                collab.product_id,
                data.actor_id,
                collab.collaborator_id,
            )
        recipient_email = await self._notify_target(collab)
        # Capture pre-mutation status: an in-app "access revoked"
        # notification only makes sense when the recipient had real
        # access. Pending invites are surfaced through the existing
        # ``invite_sent`` snapshot republish below.
        was_active = collab.status is CollaborationStatus.ACTIVE
        collab.revoke()
        if recipient_email is not None:
            await self._email_rate_limiter.register(
                actor_id=data.actor_id,
                recipient=recipient_email,
                ip=data.actor_ip,
            )
        await self._transaction.commit()
        if recipient_email is not None:
            base = self._security.frontend_base_url.rstrip("/")
            link = f"{base}/products/{collab.product_id}"
            await self._scheduler.schedule_send_email(
                to=recipient_email,
                subject="Доступ к продукту отозван",
                components=[
                    EmailParagraph.text("Здравствуйте!"),
                    EmailParagraph.text(
                        "Доступ к продукту был отозван. Если это произошло "
                        "по ошибке — свяжитесь с автором продукта.",
                    ),
                    EmailButton(label="Открыть Learnic", url=link),
                ],
            )
        await publish_product_event(
            self._event_bus,
            payload=CollaborationRevokedPayload.of(
                collaboration_id=collab.oid,
                collaborator_id=collab.collaborator_id,
            ),
            product_id=collab.product_id,
            actor_id=data.actor_id,
        )
        recipient_id = await self._notification_recipient(collab)
        if recipient_id is not None:
            await self._notifications.republish_for_collaboration(
                recipient_id=recipient_id,
                collaboration_id=collab.oid,
            )
            if was_active:
                # Active collaborator was kicked — push a fresh
                # ``access_revoked`` card. Pending-invite
                # revocations stay on the recipient's existing
                # ``invite_sent`` card via the snapshot above.
                await self._notifications.publish(
                    Notification.for_access_revoked(
                        recipient_id=recipient_id,
                        actor_id=data.actor_id,
                        collaboration_id=collab.oid,
                        product_id=collab.product_id,
                        revoker_id=data.actor_id,
                    ),
                )

    async def _notify_target(
        self,
        collab: ProductCollaboration,
    ) -> str | None:
        if collab.collaborator_id is not None:
            user = await self._user_gateway.with_id(collab.collaborator_id)
            if user is not None:
                return user.email.value
        if collab.invited_email is not None:
            return collab.invited_email.value
        return None

    async def _notification_recipient(
        self,
        collab: ProductCollaboration,
    ) -> UserID | None:
        """Resolve who, if anyone, owns the in-app ``invite_sent`` card.

        For by-user invites the recipient is :attr:`collaborator_id`.
        For by-email invites it's whichever registered user matches
        :attr:`invited_email` (the same address we used when first
        creating the in-app card in
        :class:`InviteCollaboratorByEmailCommandHandler`); if the
        email maps to nobody, there's no card to update.
        """
        if collab.collaborator_id is not None:
            return collab.collaborator_id
        if collab.invited_email is not None:
            user = await self._user_gateway.with_email(
                collab.invited_email.value,
            )
            if user is not None:
                return user.oid
        return None
