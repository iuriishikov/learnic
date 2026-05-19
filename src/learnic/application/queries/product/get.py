from dataclasses import dataclass
from datetime import datetime
from typing import Final, final

from learnic.application.common.persistence.product import (
    ProductReader,
    ProductView,
)
from learnic.application.common.persistence.user_ref import UserRefView
from learnic.application.common.storage.file_storage import FileStorage
from learnic.application.common.validators import validate_empty
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID


@dataclass(slots=True, frozen=True)
class GetProductQuery:
    oid: ProductID


@dataclass(slots=True, frozen=True)
class ProductOutput:
    """Product projection with the cover URL already resolved.

    Mirrors :class:`ProductView` field-for-field except the cover —
    instead of leaking the persistence-layer ``FileView``, the handler
    presigns a short-lived storage URL via :class:`FileStorage` and
    surfaces it as ``cover_url`` so HTTP routes / SPAs can render the
    image directly. ``None`` means the product has no cover attached.
    """

    oid: ProductID
    type: ProductType
    status: ProductStatus
    name: str
    description: str | None
    total_duration_in_hours: int | None
    author: UserRefView
    cover_url: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class PaginatedProductsOutput:
    """A page of :class:`ProductOutput` plus the total match count.

    ``total`` is the count of products matching the same filter as
    ``items`` **without** pagination — the numerator the SPA needs
    to render numbered page controls (``Math.ceil(total / per_page)``).
    Routes surface ``total`` via the ``X-Total-Count`` response header
    so the JSON body stays a plain ``list[ProductSchema]`` and existing
    clients don't break.
    """

    items: list["ProductOutput"]
    total: int


async def resolve_product_output(
    view: ProductView,
    file_storage: FileStorage,
) -> ProductOutput:
    """Inflate a :class:`ProductView` into a :class:`ProductOutput`.

    Single call site for cover-URL resolution; reused by the
    single-product and list-product query handlers so they share
    the same conversion logic.
    """
    cover_url: str | None = None
    if view.cover is not None:
        cover_url = await file_storage.presigned_get_url(
            view.cover.bucket,
            view.cover.storage_name,
        )
    return ProductOutput(
        oid=view.oid,
        type=view.type,
        status=view.status,
        name=view.name,
        description=view.description,
        total_duration_in_hours=view.total_duration_in_hours,
        author=view.author,
        cover_url=cover_url,
        published_at=view.published_at,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


@final
class GetProductQueryHandler:
    def __init__(
        self,
        reader: ProductReader,
        file_storage: FileStorage,
    ) -> None:
        self._reader: Final = reader
        self._file_storage: Final = file_storage

    async def run(self, data: GetProductQuery) -> ProductOutput:
        view = validate_empty(
            await self._reader.with_id(data.oid),
            data.oid,
        )
        return await resolve_product_output(view, self._file_storage)
