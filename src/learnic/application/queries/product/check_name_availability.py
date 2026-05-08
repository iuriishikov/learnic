from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.persistence.product import ProductReader
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class CheckProductNameAvailabilityQuery:
    author_id: UserID
    name: str


@dataclass(slots=True, frozen=True)
class ProductNameAvailability:
    available: bool


@final
class CheckProductNameAvailabilityQueryHandler:
    """Reports whether ``author_id`` may use ``name`` for a new product.

    Mirrors the uniqueness invariant enforced at create / rename
    time: names are unique per author across all statuses,
    case-sensitive. Different authors may share names. Intended
    as a pre-flight check for client forms — clients still get
    a definitive answer at create / rename time via
    ``ProductNameAlreadyTakenError``.
    """

    def __init__(self, reader: ProductReader) -> None:
        self._reader: Final = reader

    async def run(
        self,
        data: CheckProductNameAvailabilityQuery,
    ) -> ProductNameAvailability:
        taken = await self._reader.name_exists(data.author_id, data.name)
        return ProductNameAvailability(available=not taken)
