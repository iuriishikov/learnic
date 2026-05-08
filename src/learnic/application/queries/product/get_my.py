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
    author_id: UserID
    pagination: Pagination


@final
class GetMyProductsQueryHandler:
    """Returns products owned by ``author_id`` (any status), newest first."""

    def __init__(self, reader: ProductReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetMyProductsQuery) -> list[ProductView]:
        return await self._reader.for_author(
            data.author_id,
            data.pagination,
        )
