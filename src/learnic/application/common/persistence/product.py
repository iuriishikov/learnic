from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from learnic.application.common.pagination import Pagination
from learnic.entities.file.ids import FileID
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class WebinarDetailsView:
    """Read-side projection of webinar-specific defaults."""

    total_lessons: int
    default_duration_minutes: int
    allow_recording: bool
    default_max_participants: int | None
    default_stream_url: str | None
    access_window_minutes: int | None


@dataclass(slots=True, frozen=True)
class AuthorView:
    """Public author projection embedded in :class:`ProductView`."""

    oid: UserID
    first_name: str
    last_name: str
    patronymic: str | None


@dataclass(slots=True, frozen=True)
class ProductView:
    """Read-side projection of :class:`Product` returned by the Reader."""

    oid: ProductID
    type: ProductType
    status: ProductStatus
    name: str
    description: str | None
    total_duration_in_hours: int | None
    author: AuthorView
    webinar_details: WebinarDetailsView | None
    cover_file_id: FileID | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProductGateway(Protocol):
    """Write-side lookups for :class:`Product`.

    ``with_id`` returns a fully-hydrated aggregate including
    ``webinar_details`` for products of type ``WEBINAR`` (loaded
    via a follow-up query inside the adapter).
    """

    async def with_id(self, oid: ProductID) -> Product | None: ...

    async def delete(self, product: Product) -> None: ...


class ProductReader(Protocol):
    """Read-side queries returning :class:`ProductView` projections."""

    async def with_id(self, oid: ProductID) -> ProductView | None: ...

    async def for_author(
        self,
        author_id: UserID,
        pagination: Pagination,
    ) -> list[ProductView]: ...

    async def published(
        self,
        pagination: Pagination,
    ) -> list[ProductView]: ...

    async def name_exists(
        self,
        author_id: UserID,
        name: str,
        exclude_oid: ProductID | None = None,
    ) -> bool:
        """Return ``True`` if ``author_id`` already owns a product with ``name``.

        Names are unique per author, case-sensitive, across all
        statuses (including archived). Different authors may use
        the same name. Pass ``exclude_oid`` when renaming to skip
        the product being renamed.
        """
        ...
