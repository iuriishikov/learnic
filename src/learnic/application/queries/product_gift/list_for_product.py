from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.auth.authorizer import Authorizer, AuthzTarget
from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product_gift import (
    ProductGiftReader,
)
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.queries.product_gift.get_gift import (
    ProductGiftOutput,
    resolve_gift_output,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.role.permissions import Permission
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class ListProductGiftsQuery:
    actor_id: UserID
    product_id: ProductID
    pagination: Pagination


@final
class ListProductGiftsQueryHandler:
    """List the gifts issued for a product.

    Authorised to callers who can issue gifts (``MANAGE_RELEASES``),
    so the ProductEditor gift panel shows who a product was gifted to
    and the status of each gift.
    """

    def __init__(
        self,
        authorizer: Authorizer,
        reader: ProductGiftReader,
        file_storage: FileStorage,
    ) -> None:
        self._authorizer: Final = authorizer
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(
        self,
        data: ListProductGiftsQuery,
    ) -> list[ProductGiftOutput]:
        await self._authorizer.require(
            data.actor_id,
            AuthzTarget.for_product(data.product_id),
            Permission.MANAGE_RELEASES,
        )
        views = await self._reader.for_product(
            data.product_id,
            data.pagination,
        )
        return [
            await resolve_gift_output(view, self._file_storage)
            for view in views
        ]
