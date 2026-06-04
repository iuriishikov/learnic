import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.note_release.create import (
    CreateNoteReleaseCommand,
    CreateNoteReleaseCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
)
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.note_release.value_objects import (
    NoteReleaseVersion,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


def _author_id() -> UserID:
    return UserID(uuid.uuid4())


def _note(author_id: UserID) -> Product:
    return Product.create_note(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )


def _existing_release(
    product_id: ProductID,
    author_id: UserID,
    *,
    ordinal: int = 1,
    version: NoteReleaseVersion = NoteReleaseVersion(1, 0, 0),
) -> NoteRelease:
    return NoteRelease(
        oid=NoteReleaseID(uuid.uuid4()),
        product_id=product_id,
        ordinal=ordinal,
        version=version,
        kind=NoteReleaseKind.MAJOR,
        released_at=datetime.now(timezone.utc),
        released_by=author_id,
        notes=None,
    )


def _make_handler() -> tuple[
    CreateNoteReleaseCommandHandler,
    AsyncMock,
    AsyncMock,
    MagicMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    transaction = AsyncMock()
    transaction.flush = AsyncMock()
    transaction.commit = AsyncMock()
    authorizer = AsyncMock()
    authorizer.require = AsyncMock()
    saver = MagicMock()
    saver.add_one = MagicMock()
    product_gw = AsyncMock()
    release_gw = AsyncMock()
    release_gw.count_for_product = AsyncMock(return_value=0)
    snapshotter = AsyncMock()
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock()
    product_event_bus = AsyncMock()
    product_event_bus.publish = AsyncMock()
    handler = CreateNoteReleaseCommandHandler(
        transaction=transaction,
        authorizer=authorizer,
        entity_saver=saver,
        product_gateway=product_gw,
        release_gateway=release_gw,
        snapshotter=snapshotter,
        event_bus=event_bus,
        product_event_bus=product_event_bus,
    )
    return (
        handler,
        transaction,
        authorizer,
        saver,
        product_gw,
        release_gw,
        snapshotter,
        event_bus,
        product_event_bus,
    )


async def test_first_release_publishes_note_and_returns_release() -> None:
    author = _author_id()
    note = _note(author)
    (
        handler,
        tx,
        _authorizer,
        saver,
        product_gw,
        release_gw,
        snapshotter,
        _,
        product_event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.latest_for_product.return_value = None

    release = await handler.run(
        CreateNoteReleaseCommand(
            actor_id=author,
            product_id=note.oid,
            kind=NoteReleaseKind.MAJOR,
        ),
    )

    assert release.product_id == note.oid
    assert release.ordinal == 1
    assert (
        release.version.major,
        release.version.minor,
        release.version.patch,
    ) == (1, 0, 0)
    saver.add_one.assert_called_once_with(release)
    snapshotter.snapshot.assert_awaited_once_with(release)
    assert note.status.value == "published"
    tx.flush.assert_awaited_once()
    tx.commit.assert_awaited_once()
    product_event_bus.publish.assert_awaited_once()
    event = product_event_bus.publish.call_args.args[0]
    assert type(event.payload).KIND == "published"
    assert event.product_id == note.oid
    assert event.actor_id == author
    assert event.payload.status == "published"
    assert event.payload.published_at is not None


async def test_subsequent_release_does_not_change_status() -> None:
    author = _author_id()
    note = _note(author)
    note.publish()
    previous = _existing_release(
        ProductID(note.oid),
        author,
        ordinal=3,
        version=NoteReleaseVersion(1, 1, 2),
    )
    (
        handler,
        _,
        _authorizer,
        _,
        product_gw,
        release_gw,
        snapshotter,
        _,
        product_event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.latest_for_product.return_value = previous

    release = await handler.run(
        CreateNoteReleaseCommand(
            actor_id=author,
            product_id=note.oid,
            kind=NoteReleaseKind.PATCH,
        ),
    )

    assert release.ordinal == 4
    assert (
        release.version.major,
        release.version.minor,
        release.version.patch,
    ) == (1, 1, 3)
    snapshotter.snapshot.assert_awaited_once()
    product_event_bus.publish.assert_not_awaited()


async def test_release_non_owner_raises() -> None:
    author = _author_id()
    other = _author_id()
    note = _note(author)
    (
        handler,
        _,
        authorizer,
        saver,
        product_gw,
        _,
        snapshotter,
        _,
        product_event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other,
        product_id=note.oid,
        permission="manage_releases",
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            CreateNoteReleaseCommand(
                actor_id=other,
                product_id=note.oid,
                kind=NoteReleaseKind.MAJOR,
            ),
        )
    saver.add_one.assert_not_called()
    snapshotter.snapshot.assert_not_awaited()
    product_event_bus.publish.assert_not_awaited()


async def test_release_missing_product_raises() -> None:
    (
        handler,
        _,
        _authorizer,
        _,
        product_gw,
        _,
        _,
        _,
        product_event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            CreateNoteReleaseCommand(
                actor_id=_author_id(),
                product_id=ProductID(uuid.uuid4()),
                kind=NoteReleaseKind.PATCH,
            ),
        )
    product_event_bus.publish.assert_not_awaited()
