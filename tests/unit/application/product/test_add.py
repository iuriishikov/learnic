from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.product.add_course import (
    AddCourseProductCommand,
    AddCourseProductCommandHandler,
)
from learnic.application.commands.product.add_webinar import (
    AddWebinarProductCommand,
    AddWebinarProductCommandHandler,
)
from learnic.application.common.errors import ProductNameAlreadyTakenError
from learnic.entities.file.models import File
from learnic.entities.product.enums import (
    ProductStatus,
    ProductType,
)
from learnic.entities.product.errors import ProductFieldTooLongError
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


async def test_add_course_persists_product_and_returns_id(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddCourseProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    oid = await handler.run(
        AddCourseProductCommand(
            author_id=author_id,
            name="Async Python",
            description_html="<p>30h course.</p>",
            total_duration_in_hours=30,
        ),
    )

    fake_product_reader.name_exists.assert_awaited_once_with(
        author_id,
        "Async Python",
    )
    fake_html_sanitizer.sanitize.assert_called_once_with("<p>30h course.</p>")
    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, Product)
    assert saved.oid == oid
    assert saved.type is ProductType.COURSE
    assert saved.status is ProductStatus.DRAFT
    assert saved.author_id == author_id
    assert saved.webinar_details is None
    assert saved.cover_file_id is None
    fake_file_storage.put.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_add_course_with_cover_creates_file_and_uploads(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddCourseProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    cover_bytes = b"\x89PNG\r\n\x1a\nfake-png-data"
    oid = await handler.run(
        AddCourseProductCommand(
            author_id=author_id,
            name="Async Python",
            description_html="<p>30h course.</p>",
            total_duration_in_hours=30,
            cover=cover_bytes,
            cover_content_type="image/png",
        ),
    )

    # entity_saver.add_one called twice: File then Product
    assert fake_entity_saver.add_one.call_count == 2
    saved_file = fake_entity_saver.add_one.call_args_list[0].args[0]
    saved_product = fake_entity_saver.add_one.call_args_list[1].args[0]
    assert isinstance(saved_file, File)
    assert isinstance(saved_product, Product)
    assert saved_product.oid == oid
    assert saved_product.cover_file_id == saved_file.oid
    assert saved_file.uploaded_by == author_id
    assert saved_file.size_bytes.value == len(cover_bytes)
    assert saved_file.content_type.value == "image/png"
    fake_file_storage.put.assert_awaited_once()
    put_kwargs = fake_file_storage.put.call_args.kwargs
    assert put_kwargs["data"] == cover_bytes
    assert put_kwargs["content_type"] == "image/png"
    fake_transaction.flush.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_add_course_duplicate_name_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    fake_product_reader.name_exists.return_value = True
    handler = AddCourseProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    with pytest.raises(ProductNameAlreadyTakenError):
        await handler.run(
            AddCourseProductCommand(
                author_id=author_id,
                name="Async Python",
            ),
        )

    fake_entity_saver.add_one.assert_not_called()
    fake_file_storage.put.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


async def test_add_webinar_persists_product_and_details(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddWebinarProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    oid = await handler.run(
        AddWebinarProductCommand(
            author_id=author_id,
            name="Live SQL",
            description_html="<p>4-week intensive.</p>",
            total_duration_in_hours=12,
            total_lessons=8,
            default_duration_minutes=90,
            allow_recording=True,
            default_max_participants=50,
            default_stream_url="https://meet.example.com/sql",
            access_window_minutes=15,
        ),
    )

    fake_product_reader.name_exists.assert_awaited_once_with(
        author_id,
        "Live SQL",
    )
    # add_one is called twice: Product, then WebinarDetails.
    assert fake_entity_saver.add_one.call_count == 2
    product_arg = fake_entity_saver.add_one.call_args_list[0].args[0]
    details_arg = fake_entity_saver.add_one.call_args_list[1].args[0]
    assert isinstance(product_arg, Product)
    assert product_arg.oid == oid
    assert product_arg.type is ProductType.WEBINAR
    assert product_arg.webinar_details is details_arg
    assert details_arg.oid == oid
    assert details_arg.total_lessons.value == 8
    assert details_arg.default_max_participants is not None
    assert details_arg.default_max_participants.value == 50
    fake_file_storage.put.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_add_webinar_with_cover_uploads_file(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddWebinarProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    cover = b"jpeg-bytes"
    oid = await handler.run(
        AddWebinarProductCommand(
            author_id=author_id,
            name="Live SQL",
            description_html="<p>x</p>",
            total_duration_in_hours=12,
            total_lessons=8,
            default_duration_minutes=90,
            allow_recording=True,
            default_max_participants=50,
            default_stream_url=None,
            access_window_minutes=None,
            cover=cover,
            cover_content_type="image/jpeg",
        ),
    )

    # add_one called 3 times: File, Product, WebinarDetails
    assert fake_entity_saver.add_one.call_count == 3
    saved_file = fake_entity_saver.add_one.call_args_list[0].args[0]
    saved_product = fake_entity_saver.add_one.call_args_list[1].args[0]
    assert isinstance(saved_file, File)
    assert saved_product.oid == oid
    assert saved_product.cover_file_id == saved_file.oid
    fake_file_storage.put.assert_awaited_once()


async def test_add_webinar_duplicate_name_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    fake_product_reader.name_exists.return_value = True
    handler = AddWebinarProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    with pytest.raises(ProductNameAlreadyTakenError):
        await handler.run(
            AddWebinarProductCommand(
                author_id=author_id,
                name="Live SQL",
            ),
        )

    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_add_course_name_only(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddCourseProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    oid = await handler.run(
        AddCourseProductCommand(
            author_id=author_id,
            name="Just a name",
        ),
    )

    fake_html_sanitizer.sanitize.assert_not_called()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, Product)
    assert saved.oid == oid
    assert saved.description is None
    assert saved.total_duration_in_hours is None
    assert saved.cover_file_id is None
    fake_file_storage.put.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_add_webinar_name_only_skips_details(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddWebinarProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    oid = await handler.run(
        AddWebinarProductCommand(
            author_id=author_id,
            name="Bare webinar",
        ),
    )

    # Only the Product is saved — no WebinarDetails, no File.
    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, Product)
    assert saved.oid == oid
    assert saved.type is ProductType.WEBINAR
    assert saved.description is None
    assert saved.webinar_details is None
    fake_transaction.commit.assert_awaited_once()


async def test_add_course_invalid_field_does_not_commit(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_reader: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_file_storage: AsyncMock,
    fake_s3_config: MagicMock,
    author_id: UserID,
) -> None:
    handler = AddCourseProductCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_reader=fake_product_reader,
        html_sanitizer=fake_html_sanitizer,
        file_storage=fake_file_storage,
        s3_config=fake_s3_config,
    )

    with pytest.raises(ProductFieldTooLongError):
        await handler.run(
            AddCourseProductCommand(
                author_id=author_id,
                name="X" * 1000,  # exceeds TITLE_MAX_LEN
                description_html="<p>ok</p>",
                total_duration_in_hours=10,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()
