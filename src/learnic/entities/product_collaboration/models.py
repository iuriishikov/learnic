import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
from learnic.entities.product_collaboration.constants import (
    INVITE_TOKEN_TTL_DAYS,
)
from learnic.entities.product_collaboration.enums import CollaborationStatus
from learnic.entities.product_collaboration.errors import (
    CannotAcceptInThisStatusError,
    CannotMutateInactiveCollaborationError,
    CannotRevokeInThisStatusError,
    EmptyGrantsError,
    InviteTokenExpiredError,
    InviteTokenMismatchError,
)
from learnic.entities.product_collaboration.grant import CollaborationGrant
from learnic.entities.product_collaboration.ids import (
    ProductCollaborationID,
)
from learnic.entities.product_collaboration.value_objects import (
    InviteToken,
    InviteTokenHash,
)
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import Email


@dataclass
class ProductCollaboration(BaseEntity[ProductCollaborationID]):
    """A user's collaboration record on a product.

    Two invite paths converge here. ``InviteCollaboratorByUserCommand``
    builds a row with ``collaborator_id`` set and ``invited_email`` /
    ``invited_email_value`` ``None``; ``InviteCollaboratorByEmailCommand``
    builds the inverse — both with status ``PENDING_INVITE`` and a
    fresh ``invite_token_hash`` + ``invite_expires_at``. Acceptance
    fills in the missing field (``collaborator_id`` for the
    by-email path), bumps status to ``ACTIVE``, and clears the token.

    Grants are loaded out-of-band by the gateway (composition
    split, no ORM relationship) — same pattern as
    ``Product.webinar_details``. For ``ACTIVE`` collaborations the
    grant list must be non-empty (``EmptyGrantsError``); pending
    invites carry the prospective grants too so the invitee sees
    accurate scope on the accept page.
    """

    product_id: ProductID
    collaborator_id: UserID | None
    invited_email: Email | None
    status: CollaborationStatus
    invited_by: UserID
    invite_token_hash: InviteTokenHash | None
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    grants: list[CollaborationGrant] = field(default_factory=list)

    def accept(
        self,
        accepting_user_id: UserID,
        token: InviteToken,
        *,
        now: datetime | None = None,
    ) -> None:
        """Transition a ``PENDING_INVITE`` to ``ACTIVE``.

        For by-user invites ``accepting_user_id`` must equal
        ``collaborator_id``; for by-email invites the caller (an
        application handler) is expected to have already verified
        that the authenticated user's email matches
        ``invited_email`` before delegating here, after which we
        bind ``collaborator_id`` to ``accepting_user_id``.
        """
        if self.status is not CollaborationStatus.PENDING_INVITE:
            raise CannotAcceptInThisStatusError(self.status.value)
        if self.invite_token_hash is None:
            raise InviteTokenMismatchError
        if self.invite_token_hash != token.hashed():
            raise InviteTokenMismatchError
        moment = now or datetime.now(timezone.utc)
        if self.invite_expires_at is not None and moment > self.invite_expires_at:
            raise InviteTokenExpiredError
        if not self.grants:
            raise EmptyGrantsError
        self.collaborator_id = accepting_user_id
        self.status = CollaborationStatus.ACTIVE
        self.accepted_at = moment
        self.invite_token_hash = None
        self.invite_expires_at = None

    def revoke(self, *, now: datetime | None = None) -> None:
        if self.status is CollaborationStatus.REVOKED:
            raise CannotRevokeInThisStatusError
        self.status = CollaborationStatus.REVOKED
        self.revoked_at = now or datetime.now(timezone.utc)
        self.invite_token_hash = None
        self.invite_expires_at = None

    def replace_grants(self, new_grants: list[CollaborationGrant]) -> None:
        """Atomically replace the grant set.

        Allowed only on ``ACTIVE`` collaborations — pending invites
        keep their original prospective grants until accept/revoke,
        and revoked rows are immutable.
        """
        if self.status is not CollaborationStatus.ACTIVE:
            raise CannotMutateInactiveCollaborationError(
                self.status.value,
            )
        if not new_grants:
            raise EmptyGrantsError
        self.grants = list(new_grants)

    @classmethod
    def invite_existing_user(
        cls,
        product_id: ProductID,
        collaborator_id: UserID,
        invited_by: UserID,
        grants: list[CollaborationGrant],
        token: InviteToken,
        *,
        ttl_days: int = INVITE_TOKEN_TTL_DAYS,
        now: datetime | None = None,
    ) -> Self:
        if not grants:
            raise EmptyGrantsError
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=ProductCollaborationID(uuid.uuid4()),
            product_id=product_id,
            collaborator_id=collaborator_id,
            invited_email=None,
            status=CollaborationStatus.PENDING_INVITE,
            invited_by=invited_by,
            invite_token_hash=token.hashed(),
            invite_expires_at=moment + timedelta(days=ttl_days),
            created_at=moment,
            accepted_at=None,
            revoked_at=None,
            grants=list(grants),
        )

    @classmethod
    def invite_by_email(
        cls,
        product_id: ProductID,
        invited_email: Email,
        invited_by: UserID,
        grants: list[CollaborationGrant],
        token: InviteToken,
        *,
        ttl_days: int = INVITE_TOKEN_TTL_DAYS,
        now: datetime | None = None,
    ) -> Self:
        if not grants:
            raise EmptyGrantsError
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=ProductCollaborationID(uuid.uuid4()),
            product_id=product_id,
            collaborator_id=None,
            invited_email=invited_email,
            status=CollaborationStatus.PENDING_INVITE,
            invited_by=invited_by,
            invite_token_hash=token.hashed(),
            invite_expires_at=moment + timedelta(days=ttl_days),
            created_at=moment,
            accepted_at=None,
            revoked_at=None,
            grants=list(grants),
        )
