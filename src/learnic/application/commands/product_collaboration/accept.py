from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    InviteEmailMismatchError,
    NotResourceOwnerError,
)
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
from learnic.entities.product_collaboration.value_objects import InviteToken
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AcceptCollaborationInviteCommand:
    actor_id: UserID
    collaboration_id: ProductCollaborationID
    raw_token: str


@final
class AcceptCollaborationInviteCommandHandler:
    """Accept a pending invite and notify the inviter.

    Two pre-checks before delegating to ``ProductCollaboration.accept``:
    1. by-user invites: ``actor_id`` must equal ``collaborator_id``
       (otherwise an attacker who guessed the URL would impersonate
       the invitee).
    2. by-email invites: the actor's account email must match
       ``invited_email`` (otherwise a different signed-in user could
       accept on behalf of the original invitee).

    On success an "invite accepted" email goes to the inviter (per
    the project's "all notifications by email" rule).
    """

    def __init__(
        self,
        transaction: Transaction,
        collab_gateway: ProductCollaborationGateway,
        user_gateway: UserGateway,
        scheduler: TaskScheduler,
        event_bus: CollaborationEventBus,
    ) -> None:
        self._transaction: Final = transaction
        self._collab_gateway: Final = collab_gateway
        self._user_gateway: Final = user_gateway
        self._scheduler: Final = scheduler
        self._event_bus: Final = event_bus

    async def run(
        self,
        data: AcceptCollaborationInviteCommand,
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
        token = InviteToken(data.raw_token)
        collab.accept(data.actor_id, token)
        await self._transaction.commit()
        inviter = await self._user_gateway.with_id(collab.invited_by)
        if inviter is not None:
            await self._scheduler.schedule_send_collaboration_accepted_email(
                to=inviter.email.value,
                product_id=collab.product_id,
                collaborator_id=data.actor_id,
            )
        await publish_collaboration_event(
            self._event_bus,
            kind=CollaborationEventKind.ACCEPTED,
            product_id=collab.product_id,
            actor_id=data.actor_id,
            payload=CollaborationEvent.make_payload(
                collaboration_id=collab.oid,
                collaborator_id=data.actor_id,
            ),
        )
