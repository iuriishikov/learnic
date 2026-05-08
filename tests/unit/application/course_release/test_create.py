import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.course_release.create import (
    CreateCourseReleaseCommand,
    CreateCourseReleaseCommandHandler,
)
from learnic.application.common.errors import (
    EntityNotFoundError,
    InsufficientPermissionsError,
    NotACourseError,
)
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.course_release.value_objects import (
    CourseReleaseVersion,
)
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


def _author_id() -> UserID:
    return UserID(uuid.uuid4())


def _course(author_id: UserID) -> Product:
    return Product.create_course(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )


def _existing_release(
    product_id: ProductID,
    author_id: UserID,
    *,
    ordinal: int = 1,
    version: CourseReleaseVersion = CourseReleaseVersion(1, 0, 0),
) -> CourseRelease:
    return CourseRelease(
        oid=CourseReleaseID(uuid.uuid4()),
        product_id=product_id,
        ordinal=ordinal,
        version=version,
        kind=CourseReleaseKind.MAJOR,
        released_at=datetime.now(timezone.utc),
        released_by=author_id,
        notes=None,
    )


def _make_handler() -> tuple[
    CreateCourseReleaseCommandHandler,
    AsyncMock,
    AsyncMock,
    MagicMock,
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
    snapshotter = AsyncMock()
    event_bus = AsyncMock()
    event_bus.publish = AsyncMock()
    handler = CreateCourseReleaseCommandHandler(
        transaction=transaction,
        authorizer=authorizer,
        entity_saver=saver,
        product_gateway=product_gw,
        release_gateway=release_gw,
        snapshotter=snapshotter,
        event_bus=event_bus,
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
    )


async def test_first_release_publishes_course_and_returns_release() -> None:
    author = _author_id()
    course = _course(author)
    (
        handler,
        tx,
        _authorizer,
        saver,
        product_gw,
        release_gw,
        snapshotter,
        _,
    ) = _make_handler()
    product_gw.with_id.return_value = course
    release_gw.latest_for_product.return_value = None

    release = await handler.run(
        CreateCourseReleaseCommand(
            actor_id=author,
            product_id=course.oid,
            kind=CourseReleaseKind.MAJOR,
        ),
    )

    assert release.product_id == course.oid
    assert release.ordinal == 1
    assert (
        release.version.major,
        release.version.minor,
        release.version.patch,
    ) == (1, 0, 0)
    saver.add_one.assert_called_once_with(release)
    snapshotter.snapshot.assert_awaited_once_with(release)
    assert course.status.value == "published"
    tx.flush.assert_awaited_once()
    tx.commit.assert_awaited_once()


async def test_subsequent_release_does_not_change_status() -> None:
    author = _author_id()
    course = _course(author)
    course.publish()
    previous = _existing_release(
        ProductID(course.oid),
        author,
        ordinal=3,
        version=CourseReleaseVersion(1, 1, 2),
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
    ) = _make_handler()
    product_gw.with_id.return_value = course
    release_gw.latest_for_product.return_value = previous

    release = await handler.run(
        CreateCourseReleaseCommand(
            actor_id=author,
            product_id=course.oid,
            kind=CourseReleaseKind.PATCH,
        ),
    )

    assert release.ordinal == 4
    assert (
        release.version.major,
        release.version.minor,
        release.version.patch,
    ) == (1, 1, 3)
    snapshotter.snapshot.assert_awaited_once()


async def test_release_for_webinar_raises() -> None:
    author = _author_id()
    webinar = Product.create_webinar(
        author_id=author,
        name=ProductTitle("Live SQL"),
    )
    (
        handler,
        tx,
        _authorizer,
        saver,
        product_gw,
        release_gw,
        snapshotter,
        _,
    ) = _make_handler()
    product_gw.with_id.return_value = webinar

    with pytest.raises(NotACourseError):
        await handler.run(
            CreateCourseReleaseCommand(
                actor_id=author,
                product_id=webinar.oid,
                kind=CourseReleaseKind.MAJOR,
            ),
        )
    saver.add_one.assert_not_called()
    snapshotter.snapshot.assert_not_awaited()
    tx.commit.assert_not_called()


async def test_release_non_owner_raises() -> None:
    author = _author_id()
    other = _author_id()
    course = _course(author)
    (
        handler,
        _,
        authorizer,
        saver,
        product_gw,
        _,
        snapshotter,
        _,
    ) = _make_handler()
    product_gw.with_id.return_value = course
    authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=other,
        product_id=course.oid,
        permission="manage_releases",
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            CreateCourseReleaseCommand(
                actor_id=other,
                product_id=course.oid,
                kind=CourseReleaseKind.MAJOR,
            ),
        )
    saver.add_one.assert_not_called()
    snapshotter.snapshot.assert_not_awaited()


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
    ) = _make_handler()
    product_gw.with_id.return_value = None

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            CreateCourseReleaseCommand(
                actor_id=_author_id(),
                product_id=ProductID(uuid.uuid4()),
                kind=CourseReleaseKind.PATCH,
            ),
        )
