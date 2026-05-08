from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.product import (
    ProductReader,
    ProductView,
)
from learnic.application.common.validators import validate_empty
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class GetProductQuery:
    oid: ProductID


@final
class GetProductQueryHandler:
    def __init__(self, reader: ProductReader) -> None:
        self._reader: Final = reader

    async def run(self, data: GetProductQuery) -> ProductView:
        return validate_empty(
            await self._reader.with_id(data.oid),
            data.oid,
        )
