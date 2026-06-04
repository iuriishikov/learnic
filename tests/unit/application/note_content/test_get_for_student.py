import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    NoteReleaseContentView,
)
from learnic.application.queries.note_content.get_for_student import (
    GetMyNoteContentQuery,
    GetMyNoteContentQueryHandler,
)
from learnic.entities.note_release.enums import NoteReleaseKind
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


def _student() -> UserID:
    return UserID(uuid.uuid4())


def _author() -> UserID:
    return UserID(uuid.uuid4())


def _note(author_id: UserID) -> Product:
    return Product.create_note(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )


def _enrollment(
    product_id: ProductID,
    student_id: UserID,
    *,
    release_id: NoteReleaseID | None = None,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> Enrollment:
    e = Enrollment.create_note(
        student_id=student_id,
        product_id=product_id,
        release_id=release_id or NoteReleaseID(uuid.uuid4()),
    )
    e.status = status
    return e


def _content_view(
    release_id: NoteReleaseID, product_id: ProductID,
) -> NoteReleaseContentView:
    return NoteReleaseContentView(
        release_id=release_id,
        product_id=product_id,
        ordinal=1,
        major=1,
        minor=0,
        patch=0,
        kind=NoteReleaseKind.MAJOR,
        notes=None,
        released_at=datetime.now(timezone.utc),
        modules=[],
    )


def _make_handler() -> tuple[
    GetMyNoteContentQueryHandler,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    product_gw = AsyncMock()
    enrollment_gw = AsyncMock()
    release_reader = AsyncMock()
    handler = GetMyNoteContentQueryHandler(
        product_gateway=product_gw,
        enrollment_gateway=enrollment_gw,
        release_reader=release_reader,
    )
    return handler, product_gw, enrollment_gw, release_reader


async def test_returns_pinned_release_content_for_active_enrollment() -> None:
    student = _student()
    note = _note(_author())
    pinned_release_id = NoteReleaseID(uuid.uuid4())
    enrollment = _enrollment(
        ProductID(note.oid),
        student,
        release_id=pinned_release_id,
    )
    expected_view = _content_view(pinned_release_id, ProductID(note.oid))

    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment
    release_reader.get_content.return_value = expected_view

    result = await handler.run(
        GetMyNoteContentQuery(actor_id=student, product_id=note.oid),
    )
    assert result is expected_view
    release_reader.get_content.assert_awaited_once_with(pinned_release_id)


async def test_missing_product_raises_404() -> None:
    handler, product_gw, _, _ = _make_handler()
    product_gw.with_id.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyNoteContentQuery(
                actor_id=_student(),
                product_id=ProductID(uuid.uuid4()),
            ),
        )


async def test_no_enrollment_raises_404() -> None:
    note = _note(_author())
    handler, product_gw, enrollment_gw, _ = _make_handler()
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyNoteContentQuery(
                actor_id=_student(),
                product_id=note.oid,
            ),
        )


async def test_revoked_enrollment_raises_404() -> None:
    student = _student()
    note = _note(_author())
    revoked = _enrollment(
        ProductID(note.oid),
        student,
        status=EnrollmentStatus.REVOKED,
    )
    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = revoked
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyNoteContentQuery(actor_id=student, product_id=note.oid),
        )
    # Revoked → never even hits the reader.
    release_reader.get_content.assert_not_awaited()


async def test_completed_enrollment_still_sees_content() -> None:
    student = _student()
    note = _note(_author())
    pinned = NoteReleaseID(uuid.uuid4())
    # Completion lives on details.completed_at; status stays
    # ACTIVE — a completed enrollment must still see content.
    completed = _enrollment(
        ProductID(note.oid),
        student,
        release_id=pinned,
    )
    completed.mark_completed()
    expected = _content_view(pinned, ProductID(note.oid))
    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = completed
    release_reader.get_content.return_value = expected

    result = await handler.run(
        GetMyNoteContentQuery(actor_id=student, product_id=note.oid),
    )
    assert result is expected


async def test_missing_release_invariant_violation_404() -> None:
    student = _student()
    note = _note(_author())
    enrollment = _enrollment(ProductID(note.oid), student)
    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment
    release_reader.get_content.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyNoteContentQuery(actor_id=student, product_id=note.oid),
        )
