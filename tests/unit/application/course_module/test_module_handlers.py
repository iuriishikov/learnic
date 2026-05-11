import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.course_module.add import (
    AddCourseModuleCommand,
    AddCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.delete import (
    DeleteCourseModuleCommand,
    DeleteCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.rename import (
    RenameCourseModuleCommand,
    RenameCourseModuleCommandHandler,
)
from learnic.application.commands.course_module.reorder import (
    ReorderCourseModulesCommand,
    ReorderCourseModulesCommandHandler,
)
from learnic.application.commands.course_module.update_description import (
    UpdateCourseModuleDescriptionCommand,
    UpdateCourseModuleDescriptionCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    InvalidReorderError,
)
from learnic.entities.course_module.ids import CourseModuleID
from learnic.entities.course_module.models import CourseModule
from learnic.entities.course_module.value_objects import ModuleTitle
from learnic.entities.product.errors import ProductDoesNotSupportError
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


# ---- add ----


async def test_add_module_appends_at_next_position(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    existing = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("Existing"),
        position=2,
    )
    fake_module_gateway.for_product.return_value = [existing]
    handler = AddCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddCourseModuleCommand(
            actor_id=author_id,
            product_id=ProductID(course_product.oid),
            title="New",
        ),
    )

    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, CourseModule)
    assert saved.oid == oid
    assert saved.position == 3
    assert saved.title.value == "New"
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert event.kind.value == "module_added"
    assert event.product_id == course_product.oid
    assert event.actor_id == author_id
    module_payload = event.payload["module"]
    assert module_payload["oid"] == str(saved.oid)
    assert module_payload["title"] == "New"
    assert module_payload["position"] == 3
    assert module_payload["description"] is None
    assert module_payload["lessons"] == []


async def test_add_module_does_not_publish_on_validation_error(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    from learnic.entities.course_module.errors import (
        CourseModuleFieldTooLongError,
    )

    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.for_product.return_value = []
    handler = AddCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(CourseModuleFieldTooLongError):
        await handler.run(
            AddCourseModuleCommand(
                actor_id=author_id,
                product_id=ProductID(course_product.oid),
                title="x" * 1000,  # exceeds MODULE_TITLE_MAX_LEN
            ),
        )
    fake_event_bus.publish.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


async def test_add_module_first_position_is_zero(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.for_product.return_value = []
    handler = AddCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        AddCourseModuleCommand(
            actor_id=author_id,
            product_id=ProductID(course_product.oid),
            title="First",
        ),
    )
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert saved.position == 0


async def test_add_module_on_webinar_raises_not_a_course(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    webinar_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = AddCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(ProductDoesNotSupportError):
        await handler.run(
            AddCourseModuleCommand(
                actor_id=author_id,
                product_id=ProductID(webinar_product.oid),
                title="X",
            ),
        )
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_add_module_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=course_product.oid,
        permission="edit_modules",
    )
    handler = AddCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddCourseModuleCommand(
                actor_id=other_user_id,
                product_id=ProductID(course_product.oid),
                title="X",
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_add_module_missing_product_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = None
    handler = AddCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            AddCourseModuleCommand(
                actor_id=author_id,
                product_id=ProductID(uuid.uuid4()),
                title="X",
            ),
        )


# ---- rename ----


async def test_rename_module_updates_title(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.with_id.return_value = course_module
    handler = RenameCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        RenameCourseModuleCommand(
            actor_id=author_id,
            module_id=CourseModuleID(course_module.oid),
            title="Renamed",
        ),
    )
    assert course_module.title.value == "Renamed"
    fake_transaction.commit.assert_awaited_once()


async def test_rename_module_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.with_id.return_value = course_module
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=course_product.oid,
        permission="edit_modules",
    )
    handler = RenameCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            RenameCourseModuleCommand(
                actor_id=other_user_id,
                module_id=CourseModuleID(course_module.oid),
                title="Hacked",
            ),
        )
    fake_transaction.commit.assert_not_called()


# ---- update_description ----


async def test_update_description_clears_with_none(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.with_id.return_value = course_module
    handler = UpdateCourseModuleDescriptionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateCourseModuleDescriptionCommand(
            actor_id=author_id,
            module_id=CourseModuleID(course_module.oid),
            description=None,
        ),
    )
    assert course_module.description is None


async def test_update_description_sets_value(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.with_id.return_value = course_module
    handler = UpdateCourseModuleDescriptionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateCourseModuleDescriptionCommand(
            actor_id=author_id,
            module_id=CourseModuleID(course_module.oid),
            description="hello",
        ),
    )
    assert course_module.description is not None
    assert course_module.description.value == "hello"


# ---- reorder ----


async def test_reorder_modules_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    a = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("A"),
        position=0,
    )
    b = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("B"),
        position=1,
    )
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.for_product.return_value = [a, b]
    handler = ReorderCourseModulesCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ReorderCourseModulesCommand(
            actor_id=author_id,
            product_id=ProductID(course_product.oid),
            ordered_ids=[
                CourseModuleID(b.oid),
                CourseModuleID(a.oid),
            ],
        ),
    )
    fake_module_gateway.reorder.assert_awaited_once()
    fake_transaction.commit.assert_awaited_once()


async def test_reorder_modules_mismatch_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    a = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("A"),
        position=0,
    )
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.for_product.return_value = [a]
    handler = ReorderCourseModulesCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    bogus = CourseModuleID(uuid.uuid4())
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderCourseModulesCommand(
                actor_id=author_id,
                product_id=ProductID(course_product.oid),
                ordered_ids=[bogus],
            ),
        )
    fake_module_gateway.reorder.assert_not_awaited()
    fake_transaction.commit.assert_not_called()


async def test_reorder_modules_duplicate_ids_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    author_id: UserID,
) -> None:
    a = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("A"),
        position=0,
    )
    b = CourseModule.create(
        product_id=ProductID(course_product.oid),
        title=ModuleTitle("B"),
        position=1,
    )
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.for_product.return_value = [a, b]
    handler = ReorderCourseModulesCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderCourseModulesCommand(
                actor_id=author_id,
                product_id=ProductID(course_product.oid),
                ordered_ids=[
                    CourseModuleID(a.oid),
                    CourseModuleID(a.oid),
                ],
            ),
        )


# ---- delete ----


async def test_delete_module_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    course_product: Product,
    course_module: CourseModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_module_gateway.with_id.return_value = course_module
    handler = DeleteCourseModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        DeleteCourseModuleCommand(
            actor_id=author_id,
            module_id=CourseModuleID(course_module.oid),
        ),
    )
    fake_module_gateway.delete.assert_awaited_once_with(course_module)
    fake_transaction.commit.assert_awaited_once()
