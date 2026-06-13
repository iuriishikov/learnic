import uuid
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.note_release import (
    ReleaseLessonContentView,
)
from learnic.application.queries.note_content.get_release_lesson import (
    GetReleaseLessonQuery,
    GetReleaseLessonQueryHandler,
)
from learnic.entities.enrollment.enums import EnrollmentStatus
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.note_lesson.ids import NoteLessonID
from learnic.entities.note_release.ids import NoteReleaseID
from learnic.entities.product.enums import ProductVisibility
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.role.permissions import Permission
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


def _lesson_view(
    lesson_id: NoteLessonID,
    release_id: NoteReleaseID,
    product_id: ProductID,
) -> ReleaseLessonContentView:
    return ReleaseLessonContentView(
        oid=lesson_id,
        release_id=release_id,
        product_id=product_id,
        title="Intro",
        position=1,
        blocks=[],
    )


def _make_handler() -> tuple[
    GetReleaseLessonQueryHandler,
    AsyncMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    product_gw = AsyncMock()
    enrollment_gw = AsyncMock()
    authorizer = AsyncMock()
    authorizer.effective_permissions = AsyncMock(return_value=None)
    release_reader = AsyncMock()
    handler = GetReleaseLessonQueryHandler(
        product_gateway=product_gw,
        enrollment_gateway=enrollment_gw,
        authorizer=authorizer,
        release_reader=release_reader,
    )
    return handler, product_gw, enrollment_gw, authorizer, release_reader


async def test_missing_lesson_raises_404() -> None:
    handler, product_gw, _, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(
                actor_id=_student(),
                lesson_id=NoteLessonID(uuid.uuid4()),
            ),
        )
    product_gw.with_id.assert_not_awaited()


async def test_missing_product_raises_404() -> None:
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(
        lesson_id,
        NoteReleaseID(uuid.uuid4()),
        ProductID(uuid.uuid4()),
    )
    handler, product_gw, enrollment_gw, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(actor_id=_student(), lesson_id=lesson_id),
        )
    enrollment_gw.with_product_and_student.assert_not_awaited()


async def test_enrolled_pinned_release_private_published_returns_view() -> (
    None
):
    student = _student()
    note = _note(
        _author(),
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    release_id = NoteReleaseID(uuid.uuid4())
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, release_id, note.oid)
    enrollment = _enrollment(note.oid, student, release_id=release_id)

    handler, product_gw, enrollment_gw, authorizer, release_reader = (
        _make_handler()
    )
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=student, lesson_id=lesson_id),
    )
    assert result is view
    authorizer.effective_permissions.assert_not_awaited()


async def test_enrolled_other_release_private_published_raises_404() -> None:
    student = _student()
    note = _note(
        _author(),
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)
    enrollment = _enrollment(
        note.oid,
        student,
        release_id=NoteReleaseID(uuid.uuid4()),
    )

    handler, product_gw, enrollment_gw, authorizer, release_reader = (
        _make_handler()
    )
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(actor_id=student, lesson_id=lesson_id),
        )
    authorizer.effective_permissions.assert_awaited_once()


async def test_enrolled_other_release_public_published_returns_view() -> (
    None
):
    student = _student()
    note = _note(_author(), published=True)
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)
    enrollment = _enrollment(
        note.oid,
        student,
        release_id=NoteReleaseID(uuid.uuid4()),
    )

    handler, product_gw, enrollment_gw, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=student, lesson_id=lesson_id),
    )
    assert result is view


async def test_collaborator_private_published_returns_view() -> None:
    note = _note(
        _author(),
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, enrollment_gw, authorizer, release_reader = (
        _make_handler()
    )
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = None
    authorizer.effective_permissions.return_value = frozenset(
        {Permission.READ_PRODUCT},
    )

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=_student(), lesson_id=lesson_id),
    )
    assert result is view


async def test_collaborator_draft_note_returns_view() -> None:
    note = _note(_author())  # DRAFT, PUBLIC
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, enrollment_gw, authorizer, release_reader = (
        _make_handler()
    )
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = None
    authorizer.effective_permissions.return_value = frozenset(
        {Permission.READ_PRODUCT},
    )

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=_student(), lesson_id=lesson_id),
    )
    assert result is view


async def test_anonymous_public_published_returns_view() -> None:
    note = _note(_author(), published=True)
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, enrollment_gw, authorizer, release_reader = (
        _make_handler()
    )
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=None, lesson_id=lesson_id),
    )
    assert result is view
    enrollment_gw.with_product_and_student.assert_not_awaited()
    authorizer.effective_permissions.assert_not_awaited()


async def test_anonymous_private_published_raises_404() -> None:
    note = _note(
        _author(),
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, _, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(actor_id=None, lesson_id=lesson_id),
        )


async def test_anonymous_public_draft_raises_404() -> None:
    note = _note(_author())  # DRAFT, PUBLIC
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, _, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(actor_id=None, lesson_id=lesson_id),
        )


async def test_anonymous_public_archived_raises_404() -> None:
    # Closed-set discipline on ProductStatus: the open-distribution
    # rule demands PUBLISHED specifically, not merely "not DRAFT" —
    # archived notes keep their releases but leave the public
    # surface.
    note = _note(_author(), published=True)
    note.archive()
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, _, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(actor_id=None, lesson_id=lesson_id),
        )


async def test_enrolled_pinned_match_archived_returns_view() -> None:
    # The enrollment branch checks no product status: an enrolled
    # student keeps reading their pinned release after archival.
    student = _student()
    note = _note(_author(), published=True)
    note.archive()
    lesson_id = NoteLessonID(uuid.uuid4())
    pinned_release_id = NoteReleaseID(uuid.uuid4())
    view = _lesson_view(lesson_id, pinned_release_id, note.oid)
    enrollment = _enrollment(
        note.oid,
        student,
        release_id=pinned_release_id,
    )

    handler, product_gw, enrollment_gw, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = enrollment

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=student, lesson_id=lesson_id),
    )
    assert result is view


async def test_signed_in_not_enrolled_public_published_returns_view() -> (
    None
):
    note = _note(_author(), published=True)
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, NoteReleaseID(uuid.uuid4()), note.oid)

    handler, product_gw, enrollment_gw, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = None

    result = await handler.run(
        GetReleaseLessonQuery(actor_id=_student(), lesson_id=lesson_id),
    )
    assert result is view


async def test_revoked_enrollment_private_published_raises_404() -> None:
    student = _student()
    note = _note(
        _author(),
        published=True,
        visibility=ProductVisibility.PRIVATE,
    )
    release_id = NoteReleaseID(uuid.uuid4())
    lesson_id = NoteLessonID(uuid.uuid4())
    view = _lesson_view(lesson_id, release_id, note.oid)
    revoked = _enrollment(
        note.oid,
        student,
        release_id=release_id,
        status=EnrollmentStatus.REVOKED,
    )

    handler, product_gw, enrollment_gw, _, release_reader = _make_handler()
    release_reader.get_lesson.return_value = view
    product_gw.with_id.return_value = note
    enrollment_gw.with_product_and_student.return_value = revoked

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetReleaseLessonQuery(actor_id=student, lesson_id=lesson_id),
        )
