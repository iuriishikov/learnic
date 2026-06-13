import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    NoteReleaseSchemeView,
)
from learnic.application.queries.note_content.get_scheme import (
    GetNoteSchemeQuery,
    GetNoteSchemeQueryHandler,
)
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.note_release.models import NoteRelease
from learnic.entities.product.enums import ProductVisibility
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


def _student() -> UserID:
    return UserID(uuid.uuid4())


def _author() -> UserID:
    return UserID(uuid.uuid4())


def _note(
    author_id: UserID,
    *,
    published: bool = False,
    visibility: ProductVisibility = ProductVisibility.PUBLIC,
) -> Product:
    note = Product.create_note(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )
    if published:
        note.publish()
    note.change_visibility(visibility)
    return note


def _enrollment(
    product_id: ProductID,
    student_id: UserID,
    *,
    release_id: NoteReleaseID | None = None,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> Enrollment:
    enrollment = Enrollment.create_note(
        student_id=student_id,
        product_id=product_id,
        release_id=release_id or NoteReleaseID(uuid.uuid4()),
    )
    enrollment.status = status
    return enrollment


def _release(product_id: ProductID, author_id: UserID) -> NoteRelease:
    return NoteRelease.create(
        product_id=product_id,
        ordinal=1,
        previous_version=None,
        kind=NoteReleaseKind.MAJOR,
        released_by=author_id,
    )


def _scheme_view(
    release_id: NoteReleaseID, product_id: ProductID,
) -> NoteReleaseSchemeView:
    return NoteReleaseSchemeView(
        release_id=release_id,
        product_id=product_id,
        modules=[],
    )


def _make_handler() -> tuple[
    GetNoteSchemeQueryHandler,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    product_gw = AsyncMock()
    enrollment_gw = AsyncMock()
    release_gw = AsyncMock()
    release_reader = AsyncMock()
    handler = GetNoteSchemeQueryHandler(
        product_gateway=product_gw,
        enrollment_gateway=enrollment_gw,
        release_gateway=release_gw,
        release_reader=release_reader,
    )
    return handler, product_gw, enrollment_gw, release_gw, release_reader


async def test_active_enrollment_gets_pinned_release_scheme() -> None:
    student = _student()
    note = _note(_author(), published=True)
    pinned_release_id = NoteReleaseID(uuid.uuid4())
    enrollment = _enrollment(
        note.oid,
        student,
        release_id=pinned_release_id,
    )
    expected_view = _scheme_view(pinned_release_id, note.oid)

    handler, product_gw, enrollment_gw, release_gw, release_reader = (
        _make_handler()
    )
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment
    release_reader.get_scheme.return_value = expected_view

    result = await handler.run(
        GetNoteSchemeQuery(actor_id=student, product_id=note.oid),
    )
    assert result is expected_view
    release_reader.get_scheme.assert_awaited_once_with(pinned_release_id)
    release_gw.latest_for_product.assert_not_awaited()


async def test_anonymous_private_published_gets_latest_scheme() -> None:
    # The key contrast with the per-lesson block read: PRIVATE published
    # notes still serve their structure publicly.
    author = _author()
    note = _note(
        author,
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    latest = _release(note.oid, author)
    expected_view = _scheme_view(latest.oid, note.oid)

    handler, product_gw, _, release_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.latest_for_product.return_value = latest
    release_reader.get_scheme.return_value = expected_view

    result = await handler.run(
        GetNoteSchemeQuery(actor_id=None, product_id=note.oid),
    )
    assert result is expected_view
    release_gw.latest_for_product.assert_awaited_once_with(note.oid)
    release_reader.get_scheme.assert_awaited_once_with(latest.oid)


async def test_anonymous_public_published_gets_latest_scheme() -> None:
    author = _author()
    note = _note(author, published=True)
    latest = _release(note.oid, author)
    expected_view = _scheme_view(latest.oid, note.oid)

    handler, product_gw, _, release_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.latest_for_product.return_value = latest
    release_reader.get_scheme.return_value = expected_view

    result = await handler.run(
        GetNoteSchemeQuery(actor_id=None, product_id=note.oid),
    )
    assert result is expected_view
    release_reader.get_scheme.assert_awaited_once_with(latest.oid)


async def test_revoked_enrollment_private_published_gets_latest_scheme() -> (
    None
):
    # Second key contrast with the per-lesson block read: a revoked
    # enrollee on a PRIVATE note falls through to the public
    # branch and still gets the latest scheme (blocks 404).
    author = _author()
    student = _student()
    note = _note(
        author,
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    revoked = _enrollment(
        note.oid,
        student,
        status=EnrollmentStatus.REVOKED,
    )
    latest = _release(note.oid, author)
    expected_view = _scheme_view(latest.oid, note.oid)

    handler, product_gw, enrollment_gw, release_gw, release_reader = (
        _make_handler()
    )
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = revoked
    release_gw.latest_for_product.return_value = latest
    release_reader.get_scheme.return_value = expected_view

    result = await handler.run(
        GetNoteSchemeQuery(actor_id=student, product_id=note.oid),
    )
    assert result is expected_view
    release_gw.latest_for_product.assert_awaited_once_with(note.oid)
    release_reader.get_scheme.assert_awaited_once_with(latest.oid)


async def test_signed_in_not_enrolled_gets_latest_scheme() -> None:
    author = _author()
    note = _note(author, published=True)
    latest = _release(note.oid, author)
    expected_view = _scheme_view(latest.oid, note.oid)

    handler, product_gw, enrollment_gw, release_gw, release_reader = (
        _make_handler()
    )
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = None
    release_gw.latest_for_product.return_value = latest
    release_reader.get_scheme.return_value = expected_view

    result = await handler.run(
        GetNoteSchemeQuery(actor_id=_student(), product_id=note.oid),
    )
    assert result is expected_view
    release_gw.latest_for_product.assert_awaited_once_with(note.oid)


async def test_anonymous_draft_note_raises_404() -> None:
    note = _note(_author())  # DRAFT, PUBLIC
    handler, product_gw, _, release_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetNoteSchemeQuery(actor_id=None, product_id=note.oid),
        )
    release_gw.latest_for_product.assert_not_awaited()
    release_reader.get_scheme.assert_not_awaited()


async def test_missing_product_raises_404() -> None:
    handler, product_gw, _, release_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetNoteSchemeQuery(
                actor_id=_student(),
                product_id=ProductID(uuid.uuid4()),
            ),
        )
    release_gw.latest_for_product.assert_not_awaited()
    release_reader.get_scheme.assert_not_awaited()


async def test_missing_release_scheme_raises_404() -> None:
    author = _author()
    note = _note(author, published=True)
    latest = _release(note.oid, author)
    handler, product_gw, _, release_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    release_gw.latest_for_product.return_value = latest
    release_reader.get_scheme.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetNoteSchemeQuery(actor_id=None, product_id=note.oid),
        )
    release_reader.get_scheme.assert_awaited_once_with(latest.oid)
