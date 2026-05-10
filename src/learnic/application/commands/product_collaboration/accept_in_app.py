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
    ProductEventBus,
    ProductEventKind,
    make_collaboration_payload,
    publish_product_event,
)
from learnic.entities.notification.models import Notification
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AcceptCollaborationInAppCommand:
    actor_id: UserID
    collaboration_id: ProductCollaborationID


@final
class AcceptCollaborationInAppCommandHandler:
    """Accept a pending invite from an in-app notification.

    Same effect as :class:`AcceptCollaborationInviteCommandHandler`
    but without the email-link token: the in-app channel is itself
    authenticated as the recipient, so the recipient identity check
    (``actor_id == collaborator_id`` for by-user invites, or
    ``actor.email == invited_email`` for by-email invites) is the
    only authorisation gate. The expiration check still applies.

    On success an in-app notification is published to the inviter,
    mirroring the email-link accept flow; the accompanying email is
    dispatched by ``NotificationPublisher`` based on the recipient's
    preference matrix.
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
        data: AcceptCollaborationInAppCommand,
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
        collab.accept_in_app(data.actor_id)
        await self._transaction.commit()
        await publish_product_event(
            self._event_bus,
            kind=ProductEventKind.COLLABORATION_ACCEPTED,
            product_id=collab.product_id,
            actor_id=data.actor_id,
            payload=make_collaboration_payload(
                collaboration_id=collab.oid,
                collaborator_id=data.actor_id,
            ),
        )
        await self._notifications.publish(
            Notification.for_invite_accepted(
                recipient_id=collab.invited_by,
                actor_id=data.actor_id,
                collaboration_id=collab.oid,
                product_id=collab.product_id,
                collaborator_id=data.actor_id,
            ),
        )
        await self._notifications.republish_for_collaboration(
            recipient_id=data.actor_id,
            collaboration_id=collab.oid,
        )
