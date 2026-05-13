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
from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.notifications.channels import EmailPayload
from learnic.application.common.notifications.notifier import Notifier
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
    ProductCollaborationSaver,
)
from learnic.application.common.persistence.role import RoleGateway
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.product_events import (
    CollaborationGrantsUpdatedPayload,
    ProductEventBus,
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
        lineage: ResourceLineageReader,
        notifier: Notifier,
        event_bus: ProductEventBus,
        security: SecurityPolicies,
    ) -> None:
        self._transaction: Final = transaction
        self._authorizer: Final = authorizer
        self._hierarchy: Final = hierarchy
        self._collab_gateway: Final = collab_gateway
        self._collab_saver: Final = collab_saver
        self._resolver: Final = GrantSpecResolver(role_gateway, lineage)
        self._notifier: Final = notifier
        self._event_bus: Final = event_bus
        self._security: Final = security

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
            base = self._security.frontend_base_url.rstrip("/")
            link = f"{base}/products/{collab.product_id}"
            await self._notifier.send(
                recipient_id=collab.collaborator_id,
                category=NotificationCategory.TEACHING,
                payloads={
                    NotificationChannel.EMAIL: EmailPayload(
                        subject="Изменены права совместной работы",
                        components=[
                            EmailParagraph.text("Здравствуйте!"),
                            EmailParagraph.text(
                                "Ваши права для совместной работы над "
                                "продуктом были обновлены.",
                            ),
                            EmailButton(label="Открыть продукт", url=link),
                        ],
                    ),
                },
            )
        await publish_product_event(
            self._event_bus,
            payload=CollaborationGrantsUpdatedPayload.of(
                collaboration_id=collab.oid,
                collaborator_id=collab.collaborator_id,
            ),
            product_id=collab.product_id,
            actor_id=data.actor_id,
        )
