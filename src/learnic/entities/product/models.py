import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID
from learnic.entities.product.capabilities import (
    PRODUCT_TYPE_CAPABILITIES,
    ProductCapability,
)
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
    ProductVisibility,
)
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import (
    DurationHours,
    ProductDescription,
    ProductTitle,
)
from learnic.entities.user.models import UserID


@dataclass
class Product(BaseEntity[ProductID]):
    """A user-owned learning product (course only at this phase).

    Only ``name`` is a required identity field at creation time —
    every other piece of metadata (``description``,
    ``total_duration_in_hours``, ``cover_file_id``) is optional
    and starts as ``None``.
    """

    author_id: UserID
    type: ProductType
    name: ProductTitle
    status: ProductStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    visibility: ProductVisibility = ProductVisibility.PUBLIC
    description: ProductDescription | None = None
    total_duration_in_hours: DurationHours | None = None
    cover_file_id: FileID | None = None

    def supports(self, capability: ProductCapability) -> bool:
        """Return whether this product's type advertises ``capability``."""
        return capability in PRODUCT_TYPE_CAPABILITIES[self.type]

    def require_supports(self, capability: ProductCapability) -> None:
        """Raise :class:`ProductDoesNotSupportError` if ``capability`` is unsupported.

        Gates type-specific operations from one place instead of
        repeating ``if product.type is not ProductType.X: raise NotAXError``
        in every handler.
        """
        if not self.supports(capability):
            raise ProductDoesNotSupportError(
                product_id=self.oid,
                product_type=self.type.value,
                capability=capability.value,
            )

    def rename(self, new_name: ProductTitle) -> None:
        self.name = new_name

    def change_description(
        self,
        new_description: ProductDescription,
    ) -> None:
        self.description = new_description

    def change_total_duration(self, new_duration: DurationHours) -> None:
        self.total_duration_in_hours = new_duration

    def set_cover(self, file_id: FileID) -> FileID | None:
        """Attach ``file_id`` as cover, returning the previous one (if any)."""
        previous = self.cover_file_id
        self.cover_file_id = file_id
        return previous

    def remove_cover(self) -> FileID | None:
        previous = self.cover_file_id
        self.cover_file_id = None
        return previous

    def publish(self) -> None:
        if self.status is ProductStatus.PUBLISHED:
            return
        self.status = ProductStatus.PUBLISHED
        self.published_at = datetime.now(timezone.utc)

    def change_visibility(self, visibility: ProductVisibility) -> None:
        """Set the product's discovery visibility (public ⇄ private).

        Idempotent: re-applying the current visibility is a no-op the
        caller can detect by comparing before/after to decide whether
        to emit a change event.
        """
        self.visibility = visibility

    def archive(self) -> None:
        self.status = ProductStatus.ARCHIVED

    def unarchive(self) -> None:
        """Restore an archived product to its prior lifecycle state.

        ``published_at`` is preserved on archive, so it is the
        authoritative signal: a non-``None`` value means the product
        was previously published (webinar via ``publish()``, course
        via first release) and is restored to ``PUBLISHED``;
        otherwise the product returns to ``DRAFT``.
        """
        if self.published_at is not None:
            self.status = ProductStatus.PUBLISHED
        else:
            self.status = ProductStatus.DRAFT

    @classmethod
    def create_course(
        cls,
        author_id: UserID,
        name: ProductTitle,
        description: ProductDescription | None = None,
        total_duration_in_hours: DurationHours | None = None,
        cover_file_id: FileID | None = None,
    ) -> Self:
        now = datetime.now(timezone.utc)
        return cls(
            oid=ProductID(uuid.uuid4()),
            author_id=author_id,
            type=ProductType.COURSE,
            name=name,
            description=description,
            total_duration_in_hours=total_duration_in_hours,
            status=ProductStatus.DRAFT,
            published_at=None,
            created_at=now,
            updated_at=now,
            cover_file_id=cover_file_id,
        )
