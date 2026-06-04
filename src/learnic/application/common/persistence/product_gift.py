from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.user import UserView
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.product_gift.models import ProductGift
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ProductGiftView:
    """Read-side projection of a :class:`ProductGift`.

    Enriched with the product name and the gifter reference so the
    email-link landing page (``/gifts/{id}/accept``) can render
    "<gifter> gifted you <product>" without extra round-trips —
    the gift URL carries no product context of its own.
    """

    oid: ProductGiftID
    product_id: ProductID
    product_name: str
    recipient: UserView | None
    invited_email: str | None
    status: GiftStatus
    gifter: UserView
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None


class ProductGiftGateway(Protocol):
    """Write-side lookups for :class:`ProductGift`.

    A gift has no child rows (unlike collaboration grants), so the
    parent entity is persisted through the generic ``EntitySaver``;
    this gateway only exposes the read-for-write lookups and the
    periodic expiry purge.
    """

    async def with_id(
        self,
        oid: ProductGiftID,
    ) -> ProductGift | None: ...

    async def active_for_product_and_user(
        self,
        product_id: ProductID,
        recipient_id: UserID,
    ) -> ProductGift | None:
        """Return the pending or accepted gift for ``(product, user)``.

        Excludes ``REVOKED`` / ``DECLINED`` rows. Used by invite
        handlers to guard against gifting the same product twice to
        a user who already has a live (pending or accepted) gift.
        """
        ...

    async def pending_for_product_and_email(
        self,
        product_id: ProductID,
        invited_email: str,
    ) -> ProductGift | None:
        """Return the pending email gift for ``(product, email)``.

        Used to prevent issuing two pending email gifts to the same
        address for the same product.
        """
        ...

    async def count_email_invites_by_actor_since(
        self,
        actor_id: UserID,
        since: datetime,
    ) -> int:
        """Count email gifts issued by ``actor_id`` since ``since``.

        Used by ``InviteGiftByEmailCommandHandler`` to enforce a
        per-actor daily cap so a compromised account cannot drain the
        email provider's quota with a flood of gifts to attacker-
        controlled addresses. Counts every row created in the window
        across all products — accepted and revoked rows included,
        because the email (and the upstream token) was already spent
        regardless of later state.
        """
        ...

    async def delete_expired_pending_invites(
        self,
        expires_before: datetime,
    ) -> int:
        """Delete ``PENDING_INVITE`` rows past their ``invite_expires_at``.

        Used by ``PurgeExpiredGiftsCommandHandler`` as a periodic
        sweep: acceptance only validates the TTL at call time and
        never cleans up, so expired pending rows accumulate and keep
        the partial unique index on ``(product_id, invited_email)``
        for pending gifts occupied. The strict ``invite_expires_at <
        expires_before`` bound matches the validation logic on
        :meth:`ProductGift.accept` exactly — rows that would still be
        acceptable are never touched. Returns the number of deleted
        rows so the caller can log the sweep size.
        """
        ...


class ProductGiftReader(Protocol):
    """Read-side queries returning :class:`ProductGiftView`."""

    async def with_id(
        self,
        oid: ProductGiftID,
    ) -> ProductGiftView | None: ...

    async def for_product(
        self,
        product_id: ProductID,
        pagination: Pagination,
    ) -> list[ProductGiftView]: ...

    async def for_user(
        self,
        recipient_id: UserID,
        pagination: Pagination,
    ) -> list[ProductGiftView]: ...
