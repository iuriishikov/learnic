import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.application.commands.note_draft.reset import (
    ResetNoteDraftCommand,
    ResetNoteDraftCommandHandler,
)
from learnic.application.common.collaboration import DraftResetPayload
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
from learnic.entities.product.errors import ProductDoesNotSupportError
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


def _release(
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
    ResetNoteDraftCommandHandler,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    transaction = AsyncMock()
    transaction.commit = AsyncMock()
    authorizer = AsyncMock()
    authorizer.require = AsyncMock()
    product_gw = AsyncMock()
    release_gw = AsyncMock()
    resetter = AsyncMock()
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock()
    handler = ResetNoteDraftCommandHandler(
        transaction=transaction,
        authorizer=authorizer,
        product_gateway=product_gw,
        release_gateway=release_gw,
        resetter=resetter,
        event_bus=event_bus,
    )
    return (
        handler,
        transaction,
        authorizer,
        product_gw,
        release_gw,
        resetter,
        event_bus,
    )


async def test_reset_rehydrates_draft_and_publishes_event() -> None:
    author = _author_id()
    note = _note(author)
    release = _release(
        note.oid, author, ordinal=2, version=NoteReleaseVersion(1, 1, 0)
    )
    (
        handler,
        tx,
        _authorizer,
        product_gw,
        release_gw,
        resetter,
        event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.with_id.return_value = release

    await handler.run(
        ResetNoteDraftCommand(
            actor_id=author,
            product_id=note.oid,
            release_id=release.oid,
        ),
    )

    resetter.reset.assert_awaited_once_with(release)
    tx.commit.assert_awaited_once()
    event_bus.publish.assert_awaited_once()
    published = event_bus.publish.await_args.args[0]
    assert published.product_id == note.oid
    assert published.actor_id == author
    assert published.payload == DraftResetPayload(
        release_id=str(release.oid),
        ordinal=2,
        version=[1, 1, 0],
    )


async def test_reset_missing_product_raises() -> None:
    (
        handler,
        tx,
        _authorizer,
        product_gw,
        _,
        resetter,
        event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ResetNoteDraftCommand(
                actor_id=_author_id(),
                product_id=ProductID(uuid.uuid4()),
                release_id=NoteReleaseID(uuid.uuid4()),
            ),
        )
    resetter.reset.assert_not_awaited()
    tx.commit.assert_not_awaited()
    event_bus.publish.assert_not_awaited()


async def test_reset_non_owner_raises() -> None:
    author = _author_id()
    other = _author_id()
    note = _note(author)
    (
        handler,
        tx,
        authorizer,
        product_gw,
        _,
        resetter,
        event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other,
        product_id=note.oid,
        permission="manage_releases",
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            ResetNoteDraftCommand(
                actor_id=other,
                product_id=note.oid,
                release_id=NoteReleaseID(uuid.uuid4()),
            ),
        )
    resetter.reset.assert_not_awaited()
    tx.commit.assert_not_awaited()
    event_bus.publish.assert_not_awaited()


async def test_reset_release_not_found_raises() -> None:
    author = _author_id()
    note = _note(author)
    (
        handler,
        tx,
        _authorizer,
        product_gw,
        release_gw,
        resetter,
        event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.with_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ResetNoteDraftCommand(
                actor_id=author,
                product_id=note.oid,
                release_id=NoteReleaseID(uuid.uuid4()),
            ),
        )
    resetter.reset.assert_not_awaited()
    tx.commit.assert_not_awaited()
    event_bus.publish.assert_not_awaited()


async def test_reset_release_belongs_to_other_note_raises() -> None:
    author = _author_id()
    note = _note(author)
    other_note = _note(author)
    foreign_release = _release(other_note.oid, author)
    (
        handler,
        tx,
        _authorizer,
        product_gw,
        release_gw,
        resetter,
        event_bus,
    ) = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.with_id.return_value = foreign_release

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            ResetNoteDraftCommand(
                actor_id=author,
                product_id=note.oid,
                release_id=foreign_release.oid,
            ),
        )
    resetter.reset.assert_not_awaited()
    tx.commit.assert_not_awaited()
    event_bus.publish.assert_not_awaited()
