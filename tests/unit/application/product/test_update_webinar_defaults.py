from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.product.update_webinar_defaults import (
    UpdateWebinarDefaultsCommand,
    UpdateWebinarDefaultsCommandHandler,
)
from learnic.application.common.errors import (
    InsufficientPermissionsError,
    NotAWebinarError,
)
from learnic.entities.product.errors import InvalidWebinarLessonsError
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.product.webinar_details import WebinarDetails
from learnic.entities.user.models import UserID


async def test_update_replaces_all_fields(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = UpdateWebinarDefaultsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=MagicMock(),
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateWebinarDefaultsCommand(
            actor_id=author_id,
            product_id=webinar_product.oid,
            total_lessons=12,
            default_duration_minutes=120,
            allow_recording=False,
            default_max_participants=25,
            default_stream_url="https://meet.example.com/new",
            access_window_minutes=20,
        ),
    )

    details = webinar_product.webinar_details
    assert details is not None
    assert details.total_lessons.value == 12
    assert details.default_duration_minutes.value == 120
    assert details.allow_recording is False
    assert details.default_max_participants is not None
    assert details.default_max_participants.value == 25
    assert details.default_stream_url is not None
    assert details.default_stream_url.value == "https://meet.example.com/new"
    assert details.access_window_minutes is not None
    assert details.access_window_minutes.value == 20
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "webinar_defaults_updated"
    assert event.product_id == webinar_product.oid
    assert event.actor_id == author_id
    assert event.payload == {
        "total_lessons": 12,
        "default_duration_minutes": 120,
        "allow_recording": False,
        "default_max_participants": 25,
        "default_stream_url": "https://meet.example.com/new",
        "access_window_minutes": 20,
    }


async def test_update_clears_optional_fields_with_none(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = UpdateWebinarDefaultsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=MagicMock(),
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateWebinarDefaultsCommand(
            actor_id=author_id,
            product_id=webinar_product.oid,
            total_lessons=4,
            default_duration_minutes=90,
            allow_recording=True,
            default_max_participants=None,
            default_stream_url=None,
            access_window_minutes=None,
        ),
    )

    details = webinar_product.webinar_details
    assert details is not None
    assert details.default_max_participants is None
    assert details.default_stream_url is None
    assert details.access_window_minutes is None
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.payload["default_max_participants"] is None
    assert event.payload["default_stream_url"] is None
    assert event.payload["access_window_minutes"] is None


async def test_update_on_course_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    handler = UpdateWebinarDefaultsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=MagicMock(),
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(NotAWebinarError):
        await handler.run(
            UpdateWebinarDefaultsCommand(
                actor_id=author_id,
                product_id=course_product.oid,
                total_lessons=4,
                default_duration_minutes=90,
                allow_recording=True,
                default_max_participants=None,
                default_stream_url=None,
                access_window_minutes=None,
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_awaited()


async def test_update_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=webinar_product.oid,
        permission="edit_description",
    )
    handler = UpdateWebinarDefaultsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=MagicMock(),
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            UpdateWebinarDefaultsCommand(
                actor_id=other_user_id,
                product_id=webinar_product.oid,
                total_lessons=4,
                default_duration_minutes=90,
                allow_recording=True,
                default_max_participants=None,
                default_stream_url=None,
                access_window_minutes=None,
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_awaited()


async def test_update_creates_details_when_missing(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    author_id: UserID,
) -> None:
    bare_webinar = Product.create_webinar(
        author_id=author_id,
        name=ProductTitle("Bare draft"),
    )
    assert bare_webinar.webinar_details is None
    fake_product_gateway.with_id.return_value = bare_webinar
    handler = UpdateWebinarDefaultsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateWebinarDefaultsCommand(
            actor_id=author_id,
            product_id=bare_webinar.oid,
            total_lessons=6,
            default_duration_minutes=90,
            allow_recording=True,
            default_max_participants=None,
            default_stream_url=None,
            access_window_minutes=None,
        ),
    )

    details = bare_webinar.webinar_details
    assert details is not None
    assert details.oid == bare_webinar.oid
    assert details.total_lessons.value == 6
    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, WebinarDetails)
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "webinar_defaults_updated"
    assert event.payload["total_lessons"] == 6


async def test_update_invalid_lessons_raises_field_error(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = UpdateWebinarDefaultsCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=MagicMock(),
        product_gateway=fake_product_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InvalidWebinarLessonsError):
        await handler.run(
            UpdateWebinarDefaultsCommand(
                actor_id=author_id,
                product_id=webinar_product.oid,
                total_lessons=0,  # below WEBINAR_LESSONS_MIN
                default_duration_minutes=90,
                allow_recording=True,
                default_max_participants=None,
                default_stream_url=None,
                access_window_minutes=None,
            ),
        )
    fake_transaction.commit.assert_not_called()
    fake_event_bus.publish.assert_not_awaited()
