from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.role_hierarchy import RoleHierarchy
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_collaboration_events import (
    CollaborationEvent,
    CollaborationEventBus,
    CollaborationEventKind,
    publish_collaboration_event,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
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
        event_bus: CollaborationEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy
        self._collab_gateway: Final = collab_gateway
        self._user_gateway: Final = user_gateway
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus

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
        collab.revoke()
        await self._transaction.commit()
        if recipient_email is not None:
            await self._scheduler.schedule_send_collaboration_revoked_email(
                to=recipient_email,
                product_id=collab.product_id,
            )
        await publish_collaboration_event(
            self._event_bus,
            kind=CollaborationEventKind.REVOKED,
            product_id=collab.product_id,
            actor_id=data.actor_id,
            payload=CollaborationEvent.make_payload(
                collaboration_id=collab.oid,
                collaborator_id=collab.collaborator_id,
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
