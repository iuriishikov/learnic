from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.email.components import (
    EmailButton,
    EmailParagraph,
)
from learnic.application.common.email.rate_limit import (
    EmailSendRateLimiter,
)
from learnic.application.common.errors import (
    CollaborationAlreadyExistsError,
    EmailInviteRateLimitExceededError,
    EntityNotFoundError,
)
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
    ProductCollaborationSaver,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    CollaborationInvitedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.application.common.security.policies import SecurityPolicies
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.application.commands.product_collaboration.invite_by_email import (
    EMAIL_INVITE_RATE_LIMIT_WINDOW,
    MAX_EMAIL_INVITES_PER_DAY,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_TTL_DAYS,
)
from learnic.entities.product_collaboration.grant import CollaborationGrant
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
class ReinviteCollaboratorCommand:
    actor_id: UserID
    source_collaboration_id: ProductCollaborationID
    actor_ip: str | None


@final
class ReinviteCollaboratorCommandHandler:
    """Re-invite a collaborator after a previous declined/revoked invite.

    Reads the source collaboration row to recover the original target
    (registered user id or email) and the original grants, then issues
    a fresh invitation with the same scope. The previous row stays in
    its terminal state for audit; this command only ever creates a new
    ``PENDING_INVITE`` collaboration.

    Authorisation gate is identical to the original invite flow —
    caller must hold ``MANAGE_COLLABORATORS`` on the source
    product. The role-hierarchy guard from the original invite is
    not re-run here because the grants are copied verbatim from a
    previously authorised invite (they were validated when the
    source row was created); re-validating would only add latency.

    Re-invite is rejected if the source collaboration is still active
    or pending, or if a sibling pending invite for the same target
    already exists — the SPA should redirect to the existing card
    instead.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        user_gateway: UserGateway,
        collab_gateway: ProductCollaborationGateway,
        collab_saver: ProductCollaborationSaver,
        scheduler: TaskScheduler,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
        security: SecurityPolicies,
        email_rate_limiter: EmailSendRateLimiter,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._user_gateway: Final = user_gateway
        self._collab_gateway: Final = collab_gateway
        self._collab_saver: Final = collab_saver
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications
        self._security: Final = security
        self._email_rate_limiter: Final = email_rate_limiter

    async def run(
        self,
        data: ReinviteCollaboratorCommand,
    ) -> ProductCollaborationID:
        source = await self._collab_gateway.with_id(
            data.source_collaboration_id,
        )
        if source is None:
            raise EntityNotFoundError(data.source_collaboration_id)
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(source.product_id),
            Permission.MANAGE_COLLABORATORS,
        )
        await self._guard_no_active_or_pending(source)
        new_grants = [
            CollaborationGrant.create(
                role_id=g.role_id,
                scope_type=g.scope_type,
                scope_id=g.scope_id,
            )
            for g in source.grants
        ]
        token = InviteToken.generate()
        if source.collaborator_id is not None:
            collab = ProductCollaboration.invite_existing_user(
                product_id=source.product_id,
                collaborator_id=source.collaborator_id,
                invited_by=data.actor_id,
                grants=new_grants,
                token=token,
            )
        elif source.invited_email is not None:
            await self._guard_email_rate_limit(data.actor_id)
            collab = ProductCollaboration.invite_by_email(
                product_id=source.product_id,
                invited_email=source.invited_email,
                invited_by=data.actor_id,
                grants=new_grants,
                token=token,
            )
        else:
            raise EntityNotFoundError(data.source_collaboration_id)
        await self._collab_saver.save(collab)
        target_email = await self._resolve_email(collab)
        if target_email is not None:
            await self._email_rate_limiter.register(
                actor_id=data.actor_id,
                recipient=target_email,
                ip=data.actor_ip,
            )
        await self._transaction.commit()
        if target_email is not None:
            base = self._security.frontend_base_url.rstrip("/")
            link = (
                f"{base}/products/{collab.product_id}"
                f"/collaboration-invitation/{collab.oid}"
                f"/accept?token={token.value}"
            )
            await self._scheduler.schedule_send_email(
                to=target_email,
                subject="Приглашение к совместной работе на Learnic",
                components=[
                    EmailParagraph.text("Здравствуйте!"),
                    EmailParagraph.text(
                        "Вас пригласили в совместную работу над продуктом на "
                        "платформе Learnic.",
                    ),
                    EmailButton(label="Принять приглашение", url=link),
                    EmailParagraph.text(
                        f"Ссылка действует {INVITE_TOKEN_TTL_DAYS} дней. "
                        "После того как вы примете приглашение, нужные "
                        "права будут выданы автоматически.",
                    ),
                ],
            )
        await publish_product_event(
            self._event_bus,
            payload=CollaborationInvitedPayload.of(
                collaboration_id=collab.oid,
                collaborator_id=collab.collaborator_id,
                invited_email=(
                    collab.invited_email.value
                    if collab.invited_email is not None
                    else None
                ),
            ),
            product_id=collab.product_id,
            actor_id=data.actor_id,
        )
        recipient_id = await self._notification_recipient(collab)
        if recipient_id is not None:
            await self._notifications.publish(
                Notification.for_invite_sent(
                    recipient_id=recipient_id,
                    actor_id=data.actor_id,
                    collaboration_id=collab.oid,
                    product_id=collab.product_id,
                ),
            )
        return collab.oid

    async def _guard_no_active_or_pending(
        self,
        source: ProductCollaboration,
    ) -> None:
        if source.collaborator_id is not None:
            existing = await self._collab_gateway.active_for_product_and_user(
                source.product_id,
                source.collaborator_id,
            )
            if existing is not None:
                raise CollaborationAlreadyExistsError(
                    product_id=source.product_id,
                    collaborator_id=source.collaborator_id,
                )
            return
        if source.invited_email is not None:
            pending = await self._collab_gateway.pending_for_product_and_email(
                source.product_id,
                source.invited_email.value,
            )
            if pending is not None:
                raise CollaborationAlreadyExistsError(
                    product_id=source.product_id,
                    invited_email=source.invited_email.value,
                )

    async def _guard_email_rate_limit(self, actor_id: UserID) -> None:
        since = datetime.now(timezone.utc) - EMAIL_INVITE_RATE_LIMIT_WINDOW
        recent = await self._collab_gateway.count_email_invites_by_actor_since(
            actor_id,
            since,
        )
        if recent >= MAX_EMAIL_INVITES_PER_DAY:
            raise EmailInviteRateLimitExceededError(
                actor_id=actor_id,
                limit=MAX_EMAIL_INVITES_PER_DAY,
                retry_after_seconds=int(
                    timedelta(days=1).total_seconds(),
                ),
            )

    async def _resolve_email(
        self,
        collab: ProductCollaboration,
    ) -> str | None:
        if collab.invited_email is not None:
            return collab.invited_email.value
        if collab.collaborator_id is not None:
            user = await self._user_gateway.with_id(collab.collaborator_id)
            if user is not None:
                return user.email.value
        return None

    async def _notification_recipient(
        self,
        collab: ProductCollaboration,
    ) -> UserID | None:
        if collab.collaborator_id is not None:
            return collab.collaborator_id
        if collab.invited_email is not None:
            user = await self._user_gateway.with_email(
                collab.invited_email.value,
            )
            if user is not None:
                return user.oid
        return None
