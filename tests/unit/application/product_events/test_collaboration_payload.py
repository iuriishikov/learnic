import uuid

from learnic.application.common.formatting import mask_email
from learnic.application.common.product_events.payloads import (
    CollaborationInvitedPayload,
)
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.user.models import UserID


def test_collaboration_invited_masks_invited_email() -> None:
    # The product WS channel fans this payload out to every READ_PRODUCT
    # subscriber, so the raw invitee address must never reach the wire.
    raw = "carol.private@example.com"
    payload = CollaborationInvitedPayload.of(
        collaboration_id=ProductCollaborationID(uuid.uuid4()),
        invited_email=raw,
    )

    assert payload.invited_email == mask_email(raw)
    assert "carol.private" not in (payload.invited_email or "")


def test_collaboration_invited_without_email_stays_none() -> None:
    payload = CollaborationInvitedPayload.of(
        collaboration_id=ProductCollaborationID(uuid.uuid4()),
        collaborator_id=UserID(uuid.uuid4()),
    )

    assert payload.invited_email is None
