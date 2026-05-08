from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.product.archive import (
    ArchiveProductCommand,
    ArchiveProductCommandHandler,
)
from learnic.application.commands.product.delete import (
    DeleteProductCommand,
    DeleteProductCommandHandler,
)
from learnic.application.commands.product.publish import (
    PublishProductCommand,
    PublishProductCommandHandler,
)
from learnic.application.commands.product.unarchive import (
    UnarchiveProductCommand,
    UnarchiveProductCommandHandler,
)
from learnic.application.common.errors import (
    CannotPublishCourseDirectlyError,
    InsufficientPermissionsError,
    NotResourceOwnerError,
    ProductNotArchivedError,
    ProductNotInDraftError,
)
from learnic.entities.product.enums import ProductStatus
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


async def test_publish_webinar_sets_status_and_published_at(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = PublishProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        PublishProductCommand(
            actor_id=author_id,
            product_id=webinar_product.oid,
        ),
    )

    assert webinar_product.status is ProductStatus.PUBLISHED
    assert webinar_product.published_at is not None
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "published"
    assert event.product_id == webinar_product.oid
    assert event.payload["status"] == "published"
    assert event.payload["published_at"] is not None


async def test_publish_webinar_idempotent_on_already_published(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    webinar_product.publish()
    first_published_at = webinar_product.published_at
    fake_product_gateway.with_id.return_value = webinar_product
    handler = PublishProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        PublishProductCommand(
            actor_id=author_id,
            product_id=webinar_product.oid,
        ),
    )

    assert webinar_product.status is ProductStatus.PUBLISHED
    assert webinar_product.published_at == first_published_at
    fake_event_bus.publish.assert_not_called()


async def test_publish_course_directly_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = PublishProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(CannotPublishCourseDirectlyError):
        await handler.run(
            PublishProductCommand(
                actor_id=author_id,
                product_id=course_product.oid,
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_archive_sets_status_archived(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = ArchiveProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ArchiveProductCommand(
            actor_id=author_id,
            product_id=course_product.oid,
        ),
    )

    assert course_product.status is ProductStatus.ARCHIVED
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "archived"
    assert event.payload == {"status": "archived"}


async def test_unarchive_draft_returns_to_draft(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    course_product.archive()
    fake_product_gateway.with_id.return_value = course_product
    handler = UnarchiveProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UnarchiveProductCommand(
            actor_id=author_id,
            product_id=course_product.oid,
        ),
    )

    assert course_product.status is ProductStatus.DRAFT
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "unarchived"
    assert event.payload == {"status": "draft"}


async def test_unarchive_previously_published_returns_to_published(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    webinar_product.publish()
    webinar_product.archive()
    fake_product_gateway.with_id.return_value = webinar_product
    handler = UnarchiveProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UnarchiveProductCommand(
            actor_id=author_id,
            product_id=webinar_product.oid,
        ),
    )

    assert webinar_product.status is ProductStatus.PUBLISHED
    fake_transaction.commit.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.payload == {"status": "published"}


async def test_unarchive_non_archived_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = UnarchiveProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(ProductNotArchivedError):
        await handler.run(
            UnarchiveProductCommand(
                actor_id=author_id,
                product_id=course_product.oid,
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_unarchive_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    other_user_id: UserID,
) -> None:
    course_product.archive()
    fake_product_gateway.with_id.return_value = course_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=course_product.oid,
        permission="archive",
    )
    handler = UnarchiveProductCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            UnarchiveProductCommand(
                actor_id=other_user_id,
                product_id=course_product.oid,
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_delete_draft_product_succeeds(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = DeleteProductCommandHandler(
        transaction=fake_transaction,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        DeleteProductCommand(
            actor_id=author_id,
            product_id=course_product.oid,
        ),
    )

    fake_product_gateway.delete.assert_awaited_once_with(course_product)
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "deleted"
    assert event.product_id == course_product.oid


async def test_delete_published_product_raises(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    course_product.publish()
    fake_product_gateway.with_id.return_value = course_product
    handler = DeleteProductCommandHandler(
        transaction=fake_transaction,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(ProductNotInDraftError):
        await handler.run(
            DeleteProductCommand(
                actor_id=author_id,
                product_id=course_product.oid,
            ),
        )
    fake_product_gateway.delete.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()


async def test_delete_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = DeleteProductCommandHandler(
        transaction=fake_transaction,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            DeleteProductCommand(
                actor_id=other_user_id,
                product_id=course_product.oid,
            ),
        )
    fake_product_gateway.delete.assert_not_called()
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_called()
