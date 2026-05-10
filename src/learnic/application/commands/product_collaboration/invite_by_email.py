from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.resource_lineage import (
    ResourceLineageReader,
)
from learnic.application.common.auth.role_hierarchy import RoleHierarchy
from learnic.application.common.errors import (
    CannotInviteOwnerError,
    CollaborationAlreadyExistsError,
    EmailInviteRateLimitExceededError,
    EntityNotFoundError,
)
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
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.application.commands.product_collaboration._grant_spec import (
    GrantSpec,
    GrantSpecResolver,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.models import (
    ProductCollaboration,
)
from learnic.entities.product_collaboration.value_objects import InviteToken
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import Email

MAX_EMAIL_INVITES_PER_DAY: Final = 10
EMAIL_INVITE_RATE_LIMIT_WINDOW: Final = timedelta(days=1)


@dataclass(slots=True, frozen=True)
class InviteCollaboratorByEmailCommand:
    actor_id: UserID
    product_id: ProductID
    target_email: str
    grants: list[GrantSpec]


@final
class InviteCollaboratorByEmailCommandHandler:
    """Invite a (possibly unregistered) user to collaborate by email.

    Mirrors :class:`InviteCollaboratorByUserCommandHandler`, but the
    target need not have an account yet — the invite link in the
    email lands them on the SPA's accept page; if they aren't signed
    in, the SPA bounces through ``/login`` (or ``/register``) and
    returns. If the email *does* belong to a registered user and
    that user is already collaborating (active or pending), the
    handler refuses with :class:`CollaborationAlreadyExistsError`
    so the caller can switch to the by-user path.

    When the email resolves to a registered user we also push the
    same ``invite_sent`` in-app notification as the by-user path —
    otherwise the SPA's bell stays silent for invitees who happen to
    have been added by typing their address rather than picking them
    from search. Unregistered targets only get the email; their
    in-app card materialises after they sign up and accept.
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
        scheduler: TaskScheduler,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy
        self._product_gateway: Final = product_gateway
        self._user_gateway: Final = user_gateway
        self._collab_gateway: Final = collab_gateway
        self._collab_saver: Final = collab_saver
        self._resolver: Final = GrantSpecResolver(role_gateway, lineage)
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications

    async def run(
        self,
        data: InviteCollaboratorByEmailCommand,
    ) -> ProductCollaborationID:
        product = await self._product_gateway.with_id(data.product_id)
        if product is None:
            raise EntityNotFoundError(data.product_id)
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
        email = Email(data.target_email)
        # If this email already belongs to a registered user, reject
        # owner-invite and any existing active/pending collaboration.
        existing_user = await self._user_gateway.with_email(email.value)
        if existing_user is not None:
            if existing_user.oid == product.author_id:
                raise CannotInviteOwnerError(
                    data.product_id,
                    existing_user.oid,
                )
            existing = await self._collab_gateway.active_for_product_and_user(
                data.product_id,
                existing_user.oid,
            )
            if existing is not None:
                raise CollaborationAlreadyExistsError(
                    product_id=data.product_id,
                    collaborator_id=existing_user.oid,
                )
        pending = await self._collab_gateway.pending_for_product_and_email(
            data.product_id,
            email.value,
        )
        if pending is not None:
            raise CollaborationAlreadyExistsError(
                product_id=data.product_id,
                invited_email=email.value,
            )
        since = datetime.now(timezone.utc) - EMAIL_INVITE_RATE_LIMIT_WINDOW
        recent_count = (
            await self._collab_gateway.count_email_invites_by_actor_since(
                data.actor_id,
                since,
            )
        )
        if recent_count >= MAX_EMAIL_INVITES_PER_DAY:
            raise EmailInviteRateLimitExceededError(
                actor_id=data.actor_id,
                limit=MAX_EMAIL_INVITES_PER_DAY,
                retry_after_seconds=int(
                    EMAIL_INVITE_RATE_LIMIT_WINDOW.total_seconds(),
                ),
            )
        grants = await self._resolver.resolve(
            data.product_id,
            data.grants,
        )
        token = InviteToken.generate()
        collab = ProductCollaboration.invite_by_email(
            product_id=data.product_id,
            invited_email=email,
            invited_by=data.actor_id,
            grants=grants,
            token=token,
        )
        await self._collab_saver.save(collab)
        await self._transaction.commit()
        await self._scheduler.schedule_send_collaboration_invite_email(
            to=email.value,
            product_id=data.product_id,
            collaboration_id=collab.oid,
            raw_token=token.value,
        )
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.COLLABORATION_INVITED,
            product_id=data.product_id,
            actor_id=data.actor_id,
            payload=make_collaboration_payload(
                collaboration_id=collab.oid,
                invited_email=email.value,
            ),
        )
        if existing_user is not None:
            # An unregistered email has no recipient_id to address —
            # the in-app card lands once the recipient signs up and
            # accepts via the link. Registered emails get the same
            # ``invite_sent`` push as :class:`InviteCollaboratorByUserCommandHandler`.
            await self._notifications.publish(
                Notification.for_invite_sent(
                    recipient_id=existing_user.oid,
                    actor_id=data.actor_id,
                    collaboration_id=collab.oid,
                    product_id=data.product_id,
                ),
            )
        return collab.oid
