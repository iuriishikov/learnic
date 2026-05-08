import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Self

from learnic.entities.common.base_entity import BaseEntity
from learnic.entities.file.ids import FileID
from learnic.entities.product.enums import ProductStatus, ProductType
from learnic.entities.product.ids import ProductID
from learnic.entities.product.value_objects import (
    AccessWindow,
    DurationHours,
    ParticipantsLimit,
    ProductDescription,
    ProductTitle,
    StreamUrl,
    WebinarLessonsCount,
    WebinarSessionDuration,
)
from learnic.entities.product.webinar_details import WebinarDetails
from learnic.entities.user.models import UserID


@dataclass
class Product(BaseEntity[ProductID]):
    """A user-owned learning product (course or webinar).

    Only ``name`` is a required identity field at creation time —
    every other piece of metadata (``description``,
    ``total_duration_in_hours``, ``cover_file_id``, and the entire
    ``webinar_details`` sub-entity for webinar products) is optional
    and starts as ``None``. Authors fill these in incrementally via
    PATCH/PUT endpoints before publishing.

    The ``webinar_details`` slot is ``None`` for products of type
    ``COURSE`` *and* for freshly created webinar products that have
    not yet had defaults set. It is loaded out-of-band by the
    ``ProductGateway`` after the row is fetched (composition split,
    no ORM relationship), and is intentionally absent from
    imperative mapping — SQLAlchemy ignores it during load and the
    class-level ``= None`` default keeps the attribute readable on
    freshly hydrated instances.
    """

    author_id: UserID
    type: ProductType
    name: ProductTitle
    status: ProductStatus
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    description: ProductDescription | None = None
    total_duration_in_hours: DurationHours | None = None
    cover_file_id: FileID | None = None
    webinar_details: WebinarDetails | None = None

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

    def attach_webinar_details(self, details: WebinarDetails) -> None:
        """Attach freshly created webinar defaults to this product."""
        self.webinar_details = details

    def publish(self) -> None:
        if self.status is ProductStatus.PUBLISHED:
            return
        self.status = ProductStatus.PUBLISHED
        self.published_at = datetime.now(timezone.utc)

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
            webinar_details=None,
        )

    @classmethod
    def create_webinar(
        cls,
        author_id: UserID,
        name: ProductTitle,
        description: ProductDescription | None = None,
        total_duration_in_hours: DurationHours | None = None,
        *,
        total_lessons: WebinarLessonsCount | None = None,
        default_duration_minutes: WebinarSessionDuration | None = None,
        allow_recording: bool | None = None,
        default_max_participants: ParticipantsLimit | None = None,
        default_stream_url: StreamUrl | None = None,
        access_window_minutes: AccessWindow | None = None,
        cover_file_id: FileID | None = None,
    ) -> Self:
        """Create a webinar product.

        ``webinar_details`` is built only if every required default
        (``total_lessons``, ``default_duration_minutes``,
        ``allow_recording``) is provided up-front. Otherwise the
        product is created with ``webinar_details=None`` and the
        author fills in defaults later via the
        ``UpdateWebinarDefaults`` use case.
        """
        now = datetime.now(timezone.utc)
        oid = ProductID(uuid.uuid4())
        details: WebinarDetails | None = None
        if (
            total_lessons is not None
            and default_duration_minutes is not None
            and allow_recording is not None
        ):
            details = WebinarDetails.create(
                product_id=oid,
                total_lessons=total_lessons,
                default_duration_minutes=default_duration_minutes,
                allow_recording=allow_recording,
                default_max_participants=default_max_participants,
                default_stream_url=default_stream_url,
                access_window_minutes=access_window_minutes,
            )
        return cls(
            oid=oid,
            author_id=author_id,
            type=ProductType.WEBINAR,
            name=name,
            description=description,
            total_duration_in_hours=total_duration_in_hours,
            status=ProductStatus.DRAFT,
            published_at=None,
            created_at=now,
            updated_at=now,
            cover_file_id=cover_file_id,
            webinar_details=details,
        )
