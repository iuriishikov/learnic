from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.common.errors import (
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.application.common.formatting import mask_email
from learnic.application.common.persistence.product_gift import (
    ProductGiftReader,
    ProductGiftView,
)
from learnic.application.common.persistence.user import UserGateway
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.user.get import (
    UserOutput,
    resolve_user_output,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product_gift.enums import GiftStatus
from learnic.entities.product_gift.ids import ProductGiftID
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ProductGiftOutput:
    """Gift projection with embedded users resolved to ``UserOutput``.

    Mirrors :class:`ProductGiftView` but ``recipient`` / ``gifter``
    carry the unified user projection (avatar/cover presigned URLs
    signed) so the HTTP layer maps them straight to ``UserSchema``.
    ``invited_email`` is already masked.
    """

    oid: ProductGiftID
    product_id: ProductID
    product_name: str
    recipient: UserOutput | None
    invited_email: str | None
    status: GiftStatus
    gifter: UserOutput
    invite_expires_at: datetime | None
    created_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    revoked_at: datetime | None


async def resolve_gift_output(
    view: ProductGiftView,
    file_storage: FileStorage,
) -> ProductGiftOutput:
    """Inflate a :class:`ProductGiftView` into a :class:`ProductGiftOutput`.

    Single call site for gift embedded-user resolution; reused by the
    single-gift and list-gift query handlers so both emit the unified
    ``UserSchema`` shape for gifter and recipient.
    """
    return ProductGiftOutput(
        oid=view.oid,
        product_id=view.product_id,
        product_name=view.product_name,
        recipient=(
            await resolve_user_output(view.recipient, file_storage)
            if view.recipient is not None
            else None
        ),
        invited_email=(
            mask_email(view.invited_email)
            if view.invited_email is not None
            else None
        ),
        status=view.status,
        gifter=await resolve_user_output(view.gifter, file_storage),
        invite_expires_at=view.invite_expires_at,
        created_at=view.created_at,
        accepted_at=view.accepted_at,
        declined_at=view.declined_at,
        revoked_at=view.revoked_at,
    )


@dataclass(slots=True, frozen=True)
class GetGiftQuery:
    actor_id: UserID
    gift_id: ProductGiftID


@final
class GetGiftQueryHandler:
    """Load a single gift for the email-link landing page.

    Authorised to the addressee or the gifter only: the recipient
    (by id), the invited email's owner, or the user who issued the
    gift. Anyone else gets ``403`` so a guessed gift id does not leak
    the recipient's email / product. A missing gift is ``404``.
    """

    def __init__(
        self,
        reader: ProductGiftReader,
        user_gateway: UserGateway,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._user_gateway: Final = user_gateway
        self._file_storage: Final = file_storage

    async def run(self, data: GetGiftQuery) -> ProductGiftOutput:
        view = await self._reader.with_id(data.gift_id)
        if view is None:
            raise EntityNotFoundError(data.gift_id)
        if await self._is_allowed(view, data.actor_id):
            return await resolve_gift_output(view, self._file_storage)
        raise NotResourceOwnerError(data.gift_id, data.actor_id)

    async def _is_allowed(
        self,
        view: ProductGiftView,
        actor_id: UserID,
    ) -> bool:
        if view.gifter.oid == actor_id:
            return True
        if view.recipient is not None and view.recipient.oid == actor_id:
            return True
        if view.invited_email is None:
            return False
        actor = await self._user_gateway.with_id(actor_id)
        return actor is not None and actor.email.value == view.invited_email
