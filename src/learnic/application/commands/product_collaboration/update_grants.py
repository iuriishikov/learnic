from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.auth.resource_lineage import (
    ResourceLineageReader,
)
from learnic.application.common.auth.role_hierarchy import RoleHierarchy
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
    ProductCollaborationSaver,
)
from learnic.application.common.persistence.role import RoleGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_collaboration_events import (
    CollaborationEvent,
    CollaborationEventBus,
    CollaborationEventKind,
    publish_collaboration_event,
)
from learnic.application.common.tasks.scheduler import TaskScheduler
from learnic.application.commands.product_collaboration._grant_spec import (
    GrantSpec,
    GrantSpecResolver,
)
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class UpdateCollaborationGrantsCommand:
    actor_id: UserID
    collaboration_id: ProductCollaborationID
    grants: list[GrantSpec]


@final
class UpdateCollaborationGrantsCommandHandler:
    """Replace the grant set of an active collaboration.

    Caller needs ``MANAGE_COLLABORATORS`` on the product. Only
    ``ACTIVE`` collaborations are mutable (entity invariant);
    pending invites must be revoked + re-issued. After commit the
    affected collaborator (if their account email is known) is
    notified by email so they re-fetch their effective permissions.
    """

    def __init__(
        self,
        transaction: Transaction,
        authorizer: Authorizer,
        hierarchy: RoleHierarchy,
        collab_gateway: ProductCollaborationGateway,
        collab_saver: ProductCollaborationSaver,
        role_gateway: RoleGateway,
        user_gateway: UserGateway,
        lineage: ResourceLineageReader,
        scheduler: TaskScheduler,
        event_bus: CollaborationEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy
        self._collab_gateway: Final = collab_gateway
        self._collab_saver: Final = collab_saver
        self._user_gateway: Final = user_gateway
        self._resolver: Final = GrantSpecResolver(role_gateway, lineage)
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus

    async def run(
        self,
        data: UpdateCollaborationGrantsCommand,
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
        await self._hierarchy.require_can_assign_roles(
            collab.product_id,
            data.actor_id,
            [spec.role_id for spec in data.grants],
        )
        grants = await self._resolver.resolve(
            collab.product_id,
            data.grants,
        )
        collab.replace_grants(grants)
        await self._collab_saver.replace_grants(collab)
        await self._transaction.commit()
        if collab.collaborator_id is not None:
            collaborator = await self._user_gateway.with_id(
                collab.collaborator_id,
            )
            if collaborator is not None:
                await self._scheduler.schedule_send_collaboration_grants_updated_email(
                    to=collaborator.email.value,
                    product_id=collab.product_id,
                )
        await publish_collaboration_event(
            self._event_bus,
            kind=CollaborationEventKind.GRANTS_UPDATED,
            product_id=collab.product_id,
            actor_id=data.actor_id,
            payload=CollaborationEvent.make_payload(
                collaboration_id=collab.oid,
                collaborator_id=collab.collaborator_id,
            ),
        )
