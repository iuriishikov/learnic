from dataclasses import dataclass
from typing import Final, final

from learnic.application.common.errors import ProductNameAlreadyTakenError
from learnic.application.common.persistence.product import ProductReader
from learnic.application.common.persistence.transaction import (
    EntitySaver,
    Transaction,
)
from learnic.application.common.security.html import HtmlSanitizer
from learnic.application.common.storage.file_uploads import FileUploadService
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
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
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddWebinarProductCommand:
    """Create-webinar command — only ``name`` is required.

    Webinar-specific defaults (``total_lessons``,
    ``default_duration_minutes``, ``allow_recording`` and the
    optional cohort settings) may be omitted; the resulting product
    is created without ``webinar_details`` and the author fills
    them in later via ``PUT /products/{id}/webinar-defaults``.
    Providing all three required defaults up-front spawns
    ``webinar_details`` in the same transaction.
    """

    author_id: UserID
    name: str
    description_html: str | None = None
    total_duration_in_hours: int | None = None
    total_lessons: int | None = None
    default_duration_minutes: int | None = None
    allow_recording: bool | None = None
    default_max_participants: int | None = None
    default_stream_url: str | None = None
    access_window_minutes: int | None = None
    cover: bytes | None = None
    cover_content_type: str | None = None


@final
class AddWebinarProductCommandHandler:
    """Creates a new webinar product, optionally with ``WebinarDetails``.

    If ``cover`` bytes are provided, a ``File`` row is added to the
    same transaction and its ``oid`` linked via ``cover_file_id``.
    """

    def __init__(
        self,
        transaction: Transaction,
        entity_saver: EntitySaver,
        product_reader: ProductReader,
        html_sanitizer: HtmlSanitizer,
        file_uploads: FileUploadService,
    ) -> None:
        self._transaction: Final = transaction
        self._entity_saver: Final = entity_saver
        self._product_reader: Final = product_reader
        self._html_sanitizer: Final = html_sanitizer
        self._file_uploads: Final = file_uploads

    async def run(self, data: AddWebinarProductCommand) -> ProductID:
        name = ProductTitle(data.name)
        if await self._product_reader.name_exists(
            data.author_id,
            name.value,
        ):
            raise ProductNameAlreadyTakenError(name.value)

        description = self._maybe_sanitize_description(data.description_html)

        cover_file_id = await self._maybe_upload_cover(
            data.cover,
            data.cover_content_type,
            data.author_id,
        )

        product = Product.create_webinar(
            author_id=data.author_id,
            name=name,
            description=description,
            total_duration_in_hours=(
                DurationHours(data.total_duration_in_hours)
                if data.total_duration_in_hours is not None
                else None
            ),
            total_lessons=(
                WebinarLessonsCount(data.total_lessons)
                if data.total_lessons is not None
                else None
            ),
            default_duration_minutes=(
                WebinarSessionDuration(data.default_duration_minutes)
                if data.default_duration_minutes is not None
                else None
            ),
            allow_recording=data.allow_recording,
            default_max_participants=(
                ParticipantsLimit(data.default_max_participants)
                if data.default_max_participants is not None
                else None
            ),
            default_stream_url=(
                StreamUrl(data.default_stream_url)
                if data.default_stream_url is not None
                else None
            ),
            access_window_minutes=(
                AccessWindow(data.access_window_minutes)
                if data.access_window_minutes is not None
                else None
            ),
            cover_file_id=cover_file_id,
        )
        self._entity_saver.add_one(product)
        if product.webinar_details is not None:
            self._entity_saver.add_one(product.webinar_details)
        await self._transaction.commit()
        return product.oid

    def _maybe_sanitize_description(
        self,
        description_html: str | None,
    ) -> ProductDescription | None:
        if description_html is None:
            return None
        sanitized = self._html_sanitizer.sanitize(description_html)
        return ProductDescription(sanitized)

    async def _maybe_upload_cover(
        self,
        cover: bytes | None,
        cover_content_type: str | None,
        author_id: UserID,
    ) -> FileID | None:
        if cover is None or cover_content_type is None:
            return None
        file = await self._file_uploads.upload(
            cover,
            cover_content_type,
            author_id,
        )
        return file.oid
