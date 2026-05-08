from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.product.change_description import (
    ChangeProductDescriptionCommand,
    ChangeProductDescriptionCommandHandler,
)
from learnic.application.commands.product.change_name import (
    ChangeProductNameCommand,
    ChangeProductNameCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    ProductNameAlreadyTakenError,
)
from learnic.entities.product.errors import (
    EmptyProductFieldError,
    ProductFieldTooLongError,
)
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


async def test_change_name_updates_and_commits(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_product_reader: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = ChangeProductNameCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        product_reader=fake_product_reader,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ChangeProductNameCommand(
            actor_id=author_id,
            product_id=course_product.oid,
            value="Renamed",
        ),
    )

    assert course_product.name.value == "Renamed"
    fake_product_reader.name_exists.assert_awaited_once_with(
        course_product.author_id,
        "Renamed",
        exclude_oid=course_product.oid,
    )
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "name_changed"
    assert event.product_id == course_product.oid
    assert event.actor_id == author_id
    assert event.payload == {"name": "Renamed"}


async def test_change_name_to_same_value_skips_uniqueness_check(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_product_reader: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = ChangeProductNameCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        product_reader=fake_product_reader,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ChangeProductNameCommand(
            actor_id=author_id,
            product_id=course_product.oid,
            value=course_product.name.value,
        ),
    )

    fake_product_reader.name_exists.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_change_name_duplicate_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_product_reader: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_product_reader.name_exists.return_value = True
    handler = ChangeProductNameCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        product_reader=fake_product_reader,
        event_bus=fake_event_bus,
    )

    with pytest.raises(ProductNameAlreadyTakenError):
        await handler.run(
            ChangeProductNameCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                value="Already Taken",
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_change_name_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_product_reader: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=course_product.oid,
        permission="edit_description",
    )
    handler = ChangeProductNameCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        product_reader=fake_product_reader,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            ChangeProductNameCommand(
                actor_id=other_user_id,
                product_id=course_product.oid,
                value="Hacked",
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_change_name_missing_product_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_product_reader: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = None
    handler = ChangeProductNameCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        product_reader=fake_product_reader,
        event_bus=fake_event_bus,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ChangeProductNameCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                value="Whatever",
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_change_name_empty_raises_field_error(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_product_reader: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = ChangeProductNameCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        product_reader=fake_product_reader,
        event_bus=fake_event_bus,
    )

    with pytest.raises(EmptyProductFieldError):
        await handler.run(
            ChangeProductNameCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                value="   ",
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_change_description_sanitizes_before_storing(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_html_sanitizer.sanitize.side_effect = None
    fake_html_sanitizer.sanitize.return_value = "<p>safe</p>"
    handler = ChangeProductDescriptionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        html_sanitizer=fake_html_sanitizer,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ChangeProductDescriptionCommand(
            actor_id=author_id,
            product_id=course_product.oid,
            html="<script>bad</script><p>safe</p>",
        ),
    )

    fake_html_sanitizer.sanitize.assert_called_once()
    assert course_product.description.value == "<p>safe</p>"
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "description_changed"
    assert event.payload == {"description": "<p>safe</p>"}


async def test_change_description_too_long_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_html_sanitizer: MagicMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_html_sanitizer.sanitize.side_effect = lambda raw: raw  # echo
    handler = ChangeProductDescriptionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        html_sanitizer=fake_html_sanitizer,
        event_bus=fake_event_bus,
    )

    with pytest.raises(ProductFieldTooLongError):
        await handler.run(
            ChangeProductDescriptionCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                html="x" * 100_000,
            ),
        )
    fake_transaction.commit.assert_not_called()
