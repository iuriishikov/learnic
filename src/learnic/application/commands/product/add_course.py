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
from learnic.entities.common.limits import PRODUCT_LIMIT
from learnic.entities.file.ids import FileID
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import (
    DurationHours,
    ProductDescription,
    ProductTitle,
)
from learnic.entities.user.models import UserID


@dataclass(slots=True, frozen=True)
class AddCourseProductCommand:
    """Create-course command — only ``name`` is required.

    Every other field is optional and may be filled in later via
    PATCH endpoints. ``description_html`` is sanitized server-side
    before the VO is constructed; passing ``None`` (or omitting it)
    leaves the product without a description.
    """

    author_id: UserID
    name: str
    description_html: str | None = None
    total_duration_in_hours: int | None = None
    cover: bytes | None = None
    cover_content_type: str | None = None


@final
class AddCourseProductCommandHandler:
    """Creates a new course product owned by ``author_id``.

    Only ``name`` is required to spawn a draft. If ``cover`` bytes
    are provided, the handler creates a ``File`` entity, uploads
    the bytes to S3, and links the new product to it via
    ``cover_file_id``. The Product and File rows commit in the same
    transaction; only the S3 PUT happens out-of-band — a failed
    commit may leave an orphan blob, swept later by file lifecycle.
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

    async def run(self, data: AddCourseProductCommand) -> ProductID:
        PRODUCT_LIMIT.ensure(
            await self._product_reader.count_for_author(data.author_id),
        )
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

        product = Product.create_course(
            author_id=data.author_id,
            name=name,
            description=description,
            total_duration_in_hours=(
                DurationHours(data.total_duration_in_hours)
                if data.total_duration_in_hours is not None
                else None
            ),
            cover_file_id=cover_file_id,
        )
        self._entity_saver.add_one(product)
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
