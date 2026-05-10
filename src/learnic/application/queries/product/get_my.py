from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.pagination import Pagination
from learnic.application.common.persistence.product import (
    ProductReader,
    ProductView,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class GetMyProductsQuery:
    user_id: UserID
    pagination: Pagination


@final
class GetMyProductsQueryHandler:
    """Returns products the user can access (owned or active collaboration).

    A product appears in the result if ``user_id`` is its author or
    has an active collaboration on it. ``PENDING_INVITE`` and
    ``REVOKED`` collaborations are excluded. Results are ordered by
    ``created_at`` descending (any product status).
    """

    def __init__(self, reader: ProductReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetMyProductsQuery) -> list[ProductView]:
        return await self._reader.accessible_to(
            data.user_id,
            data.pagination,
        )
