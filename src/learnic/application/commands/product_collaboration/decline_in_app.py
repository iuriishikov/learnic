from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    InviteEmailMismatchError,
    NotResourceOwnerError,
)
from learnic.application.common.notifications.publisher import (
    NotificationPublisher,
)
from learnic.application.common.persistence.product_collaboration import (
    ProductCollaborationGateway,
)
from learnic.application.common.persistence.transaction import Transaction
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.product_events import (
    CollaborationDeclinedPayload,
    ProductEventBus,
    publish_product_event,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class DeclineCollaborationInAppCommand:
    actor_id: UserID
    collaboration_id: ProductCollaborationID


@final
class DeclineCollaborationInAppCommandHandler:
    """Decline a pending invite from an in-app notification.

    Mirror of :class:`AcceptCollaborationInAppCommandHandler` —
    same identity-based authorisation gate (``actor_id`` is the
    addressee), but flips the collaboration to
    :class:`CollaborationStatus.DECLINED` instead of ``ACTIVE``.

    The handler republishes the recipient's surviving
    ``invite_sent`` notification(s) tied to the collaboration so
    the panel re-renders the row as resolved without a refetch,
    and broadcasts a ``COLLABORATION_DECLINED`` product event so
    the inviter's collaborators screen reacts in real time.
    """

    def __init__(
        self,
        transaction: Transaction,
        collab_gateway: ProductCollaborationGateway,
        user_gateway: UserGateway,
        event_bus: ProductEventBus,
        notifications: NotificationPublisher,
    ) -> None:
        self._transaction: Final = transaction
        self._collab_gateway: Final = collab_gateway
        self._user_gateway: Final = user_gateway
        self._event_bus: Final = event_bus
        self._notifications: Final = notifications

    async def run(
        self,
        data: DeclineCollaborationInAppCommand,
    ) -> None:
        collab = await self._collab_gateway.with_id(data.collaboration_id)
        if collab is None:
            raise EntityNotFoundError(data.collaboration_id)
        actor = await self._user_gateway.with_id(data.actor_id)
        if actor is None:
            raise EntityNotFoundError(data.actor_id)
        if collab.collaborator_id is not None:
            if collab.collaborator_id != data.actor_id:
                raise NotResourceOwnerError(
                    collab.oid,
                    data.actor_id,
                )
        elif collab.invited_email is None or collab.invited_email != actor.email:
            raise InviteEmailMismatchError
        collab.decline_in_app(data.actor_id)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            payload=CollaborationDeclinedPayload.of(
                collaboration_id=collab.oid,
                collaborator_id=data.actor_id,
            ),
            product_id=collab.product_id,
            actor_id=data.actor_id,
        )
        await self._notifications.republish_for_collaboration(
            recipient_id=data.actor_id,
            collaboration_id=collab.oid,
        )
        # Notify the inviter that the recipient declined — gives the
        # inviter an in-app card with a re-invite CTA.
        await self._notifications.publish(
            Notification.for_invite_declined(
                recipient_id=collab.invited_by,
                actor_id=data.actor_id,
                collaboration_id=collab.oid,
                product_id=collab.product_id,
                decliner_id=data.actor_id,
            ),
        )
