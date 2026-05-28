import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.constants import GIFT_INVITE_TTL_DAYS
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.errors import (
    InviteTokenExpiredError,
    InviteTokenMismatchError,
)
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.state_machine import GiftOp, require_op
from learnic.entities.product_gift.value_objects import (
    InviteToken,
    InviteTokenHash,
)
from learnic.entities.user.models import UserID
from learnic.entities.user.value_objects import Email


@dataclass
class ProductGift(BaseEntity[ProductGiftID]):
    """A pending or resolved gift of product access to a user.

    Two invite paths converge here. ``InviteGiftByUserCommand`` builds
    a row with ``recipient_id`` set and ``invited_email`` ``None``;
    ``InviteGiftByEmailCommand`` builds the inverse — both with status
    ``PENDING_INVITE`` and a fresh ``invite_token_hash`` +
    ``invite_expires_at``. Acceptance fills in the missing field
    (``recipient_id`` for the by-email path), bumps status to
    ``ACCEPTED``, clears the token, and triggers enrollment creation
    in the application layer.

    Unlike ``ProductCollaboration`` a gift carries no grants: it
    targets a single product and, on accept, produces one enrollment.
    """

    product_id: ProductID
    recipient_id: UserID | None
    invited_email: Email | None
    status: GiftStatus
    invited_by: UserID
    invite_token_hash: InviteTokenHash | None
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None

    def accept(
        self,
        accepting_user_id: UserID,
        token: InviteToken,
        *,
        now: datetime | None = None,
    ) -> None:
        """Transition a ``PENDING_INVITE`` to ``ACCEPTED`` via email link.

        For by-user gifts ``accepting_user_id`` must equal
        ``recipient_id``; for by-email gifts the caller (an
        application handler) is expected to have already verified
        that the authenticated user's email matches ``invited_email``
        before delegating here, after which we bind ``recipient_id``
        to ``accepting_user_id``.
        """
        require_op(self.status, GiftOp.ACCEPT)
        if self.invite_token_hash is None:
            raise InviteTokenMismatchError
        if self.invite_token_hash != token.hashed():
            raise InviteTokenMismatchError
        moment = now or datetime.now(timezone.utc)
        if (
            self.invite_expires_at is not None
            and moment > self.invite_expires_at
        ):
            raise InviteTokenExpiredError
        self.recipient_id = accepting_user_id
        self.status = GiftStatus.ACCEPTED
        self.accepted_at = moment
        self.invite_token_hash = None
        self.invite_expires_at = None

    def accept_in_app(
        self,
        accepting_user_id: UserID,
        *,
        now: datetime | None = None,
    ) -> None:
        """Transition a ``PENDING_INVITE`` to ``ACCEPTED`` from in-app.

        Used when the recipient follows the accept action from an
        in-app notification rather than the email link, so no token
        is available. The caller (an application handler) MUST have
        already verified that ``accepting_user_id`` equals
        ``recipient_id`` (by-user gifts) or that the actor's email
        matches ``invited_email`` (by-email gifts). Token validation
        is skipped because the in-app channel is itself authenticated
        as the recipient.
        """
        require_op(self.status, GiftOp.ACCEPT)
        moment = now or datetime.now(timezone.utc)
        if (
            self.invite_expires_at is not None
            and moment > self.invite_expires_at
        ):
            raise InviteTokenExpiredError
        self.recipient_id = accepting_user_id
        self.status = GiftStatus.ACCEPTED
        self.accepted_at = moment
        self.invite_token_hash = None
        self.invite_expires_at = None

    def decline_in_app(
        self,
        declining_user_id: UserID,
        *,
        now: datetime | None = None,
    ) -> None:
        """Transition a ``PENDING_INVITE`` to ``DECLINED`` from in-app.

        The caller (an application handler) MUST have already
        verified that ``declining_user_id`` is the addressee — same
        identity check as :meth:`accept_in_app` (``recipient_id`` for
        by-user gifts, account email vs ``invited_email`` for
        by-email gifts).
        """
        require_op(self.status, GiftOp.DECLINE)
        moment = now or datetime.now(timezone.utc)
        if self.recipient_id is None:
            self.recipient_id = declining_user_id
        self.status = GiftStatus.DECLINED
        self.declined_at = moment
        self.invite_token_hash = None
        self.invite_expires_at = None

    def revoke(self, *, now: datetime | None = None) -> None:
        """Cancel a still-pending gift.

        Only a ``PENDING_INVITE`` gift can be revoked — an accepted
        gift has already produced an enrollment and is not undone
        through this aggregate.
        """
        require_op(self.status, GiftOp.REVOKE)
        self.status = GiftStatus.REVOKED
        self.revoked_at = now or datetime.now(timezone.utc)
        self.invite_token_hash = None
        self.invite_expires_at = None

    @classmethod
    def invite_existing_user(
        cls,
        product_id: ProductID,
        recipient_id: UserID,
        invited_by: UserID,
        token: InviteToken,
        *,
        ttl_days: int = GIFT_INVITE_TTL_DAYS,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=ProductGiftID(uuid.uuid4()),
            product_id=product_id,
            recipient_id=recipient_id,
            invited_email=None,
            status=GiftStatus.PENDING_INVITE,
            invited_by=invited_by,
            invite_token_hash=token.hashed(),
            invite_expires_at=moment + timedelta(days=ttl_days),
            created_at=moment,
            accepted_at=None,
            declined_at=None,
            revoked_at=None,
        )

    @classmethod
    def invite_by_email(
        cls,
        product_id: ProductID,
        invited_email: Email,
        invited_by: UserID,
        token: InviteToken,
        *,
        ttl_days: int = GIFT_INVITE_TTL_DAYS,
        now: datetime | None = None,
    ) -> Self:
        moment = now or datetime.now(timezone.utc)
        return cls(
            oid=ProductGiftID(uuid.uuid4()),
            product_id=product_id,
            recipient_id=None,
            invited_email=invited_email,
            status=GiftStatus.PENDING_INVITE,
            invited_by=invited_by,
            invite_token_hash=token.hashed(),
            invite_expires_at=moment + timedelta(days=ttl_days),
            created_at=moment,
            accepted_at=None,
            declined_at=None,
            revoked_at=None,
        )
