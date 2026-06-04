import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.note_module.add import (
    AddNoteModuleCommand,
    AddNoteModuleCommandHandler,
)
from learnic.application.commands.note_module.delete import (
    DeleteNoteModuleCommand,
    DeleteNoteModuleCommandHandler,
)
from learnic.application.commands.note_module.rename import (
    RenameNoteModuleCommand,
    RenameNoteModuleCommandHandler,
)
from learnic.application.commands.note_module.reorder import (
    ReorderNoteModulesCommand,
    ReorderNoteModulesCommandHandler,
)
from learnic.application.commands.note_module.update_description import (
    UpdateNoteModuleDescriptionCommand,
    UpdateNoteModuleDescriptionCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    InvalidReorderError,
)
from learnic.entities.note_module.ids import NoteModuleID
from learnic.entities.note_module.models import NoteModule
from learnic.entities.note_module.value_objects import ModuleTitle
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
    note_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    existing = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("Existing"),
        position=2,
    )
    fake_module_gateway.for_product.return_value = [existing]
    handler = AddNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    oid = await handler.run(
        AddNoteModuleCommand(
            actor_id=author_id,
            product_id=ProductID(note_product.oid),
            title="New",
        ),
    )

    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, NoteModule)
    assert saved.oid == oid
    assert saved.position == 3
    assert saved.title.value == "New"
    fake_transaction.commit.assert_awaited_once()
    fake_event_bus.publish.assert_awaited_once()
    event = fake_event_bus.publish.call_args.args[0]
    assert type(event.payload).KIND == "module_added"
    assert event.product_id == note_product.oid
    assert event.actor_id == author_id
    module_snapshot = event.payload.module
    assert module_snapshot.oid == str(saved.oid)
    assert module_snapshot.title == "New"
    assert module_snapshot.position == 3
    assert module_snapshot.description is None
    assert module_snapshot.lessons == []


async def test_add_module_does_not_publish_on_validation_error(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    author_id: UserID,
) -> None:
    from learnic.entities.note_module.errors import (
        NoteModuleFieldTooLongError,
    )

    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.for_product.return_value = []
    handler = AddNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(NoteModuleFieldTooLongError):
        await handler.run(
            AddNoteModuleCommand(
                actor_id=author_id,
                product_id=ProductID(note_product.oid),
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
    note_product: Product,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.for_product.return_value = []
    handler = AddNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        AddNoteModuleCommand(
            actor_id=author_id,
            product_id=ProductID(note_product.oid),
            title="First",
        ),
    )
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert saved.position == 0


async def test_add_module_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=note_product.oid,
        permission="edit_modules",
    )
    handler = AddNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            AddNoteModuleCommand(
                actor_id=other_user_id,
                product_id=ProductID(note_product.oid),
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
    handler = AddNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            AddNoteModuleCommand(
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
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.with_id.return_value = note_module
    handler = RenameNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        RenameNoteModuleCommand(
            actor_id=author_id,
            module_id=NoteModuleID(note_module.oid),
            title="Renamed",
        ),
    )
    assert note_module.title.value == "Renamed"
    fake_transaction.commit.assert_awaited_once()


async def test_rename_module_non_owner_raises(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    note_module: NoteModule,
    other_user_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.with_id.return_value = note_module
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other_user_id,
        product_id=note_product.oid,
        permission="edit_modules",
    )
    handler = RenameNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            RenameNoteModuleCommand(
                actor_id=other_user_id,
                module_id=NoteModuleID(note_module.oid),
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
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.with_id.return_value = note_module
    handler = UpdateNoteModuleDescriptionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateNoteModuleDescriptionCommand(
            actor_id=author_id,
            module_id=NoteModuleID(note_module.oid),
            description=None,
        ),
    )
    assert note_module.description is None


async def test_update_description_sets_value(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.with_id.return_value = note_module
    handler = UpdateNoteModuleDescriptionCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        UpdateNoteModuleDescriptionCommand(
            actor_id=author_id,
            module_id=NoteModuleID(note_module.oid),
            description="hello",
        ),
    )
    assert note_module.description is not None
    assert note_module.description.value == "hello"


# ---- reorder ----


async def test_reorder_modules_calls_gateway(
    fake_transaction: AsyncMock,
    fake_authorizer: AsyncMock,
    fake_product_gateway: AsyncMock,
    fake_module_gateway: AsyncMock,
    fake_event_bus: AsyncMock,
    note_product: Product,
    author_id: UserID,
) -> None:
    a = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("A"),
        position=0,
    )
    b = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("B"),
        position=1,
    )
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.for_product.return_value = [a, b]
    handler = ReorderNoteModulesCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        ReorderNoteModulesCommand(
            actor_id=author_id,
            product_id=ProductID(note_product.oid),
            ordered_ids=[
                NoteModuleID(b.oid),
                NoteModuleID(a.oid),
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
    note_product: Product,
    author_id: UserID,
) -> None:
    a = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("A"),
        position=0,
    )
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.for_product.return_value = [a]
    handler = ReorderNoteModulesCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    bogus = NoteModuleID(uuid.uuid4())
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderNoteModulesCommand(
                actor_id=author_id,
                product_id=ProductID(note_product.oid),
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
    note_product: Product,
    author_id: UserID,
) -> None:
    a = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("A"),
        position=0,
    )
    b = NoteModule.create(
        product_id=ProductID(note_product.oid),
        title=ModuleTitle("B"),
        position=1,
    )
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.for_product.return_value = [a, b]
    handler = ReorderNoteModulesCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )
    with pytest.raises(InvalidReorderError):
        await handler.run(
            ReorderNoteModulesCommand(
                actor_id=author_id,
                product_id=ProductID(note_product.oid),
                ordered_ids=[
                    NoteModuleID(a.oid),
                    NoteModuleID(a.oid),
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
    note_product: Product,
    note_module: NoteModule,
    author_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = note_product
    fake_module_gateway.with_id.return_value = note_module
    handler = DeleteNoteModuleCommandHandler(
        transaction=fake_transaction,
        authorizer=fake_authorizer,
        product_gateway=fake_product_gateway,
        module_gateway=fake_module_gateway,
        event_bus=fake_event_bus,
    )

    await handler.run(
        DeleteNoteModuleCommand(
            actor_id=author_id,
            module_id=NoteModuleID(note_module.oid),
        ),
    )
    fake_module_gateway.delete.assert_awaited_once_with(note_module)
    fake_transaction.commit.assert_awaited_once()
