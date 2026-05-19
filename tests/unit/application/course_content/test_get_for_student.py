import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from learnic.application.common.errors import EntityNotFoundError
from learnic.application.common.persistence.course_release import (
    CourseReleaseContentView,
)
from learnic.application.queries.course_content.get_for_student import (
    GetMyCourseContentQuery,
    GetMyCourseContentQueryHandler,
)
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
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


def _course(author_id: UserID) -> Product:
    return Product.create_course(
        author_id=author_id,
        name=ProductTitle("Async Python"),
    )


def _enrollment(
    product_id: ProductID,
    student_id: UserID,
    *,
    release_id: CourseReleaseID | None = None,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> Enrollment:
    e = Enrollment.create_course(
        student_id=student_id,
        product_id=product_id,
        release_id=release_id or CourseReleaseID(uuid.uuid4()),
    )
    e.status = status
    return e


def _content_view(
    release_id: CourseReleaseID, product_id: ProductID,
) -> CourseReleaseContentView:
    return CourseReleaseContentView(
        release_id=release_id,
        product_id=product_id,
        ordinal=1,
        major=1,
        minor=0,
        patch=0,
        kind=CourseReleaseKind.MAJOR,
        notes=None,
        released_at=datetime.now(timezone.utc),
        modules=[],
    )


def _make_handler() -> tuple[
    GetMyCourseContentQueryHandler,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    product_gw = AsyncMock()
    enrollment_gw = AsyncMock()
    release_reader = AsyncMock()
    handler = GetMyCourseContentQueryHandler(
        product_gateway=product_gw,
        enrollment_gateway=enrollment_gw,
        release_reader=release_reader,
    )
    return handler, product_gw, enrollment_gw, release_reader


async def test_returns_pinned_release_content_for_active_enrollment() -> None:
    student = _student()
    course = _course(_author())
    pinned_release_id = CourseReleaseID(uuid.uuid4())
    enrollment = _enrollment(
        ProductID(course.oid),
        student,
        release_id=pinned_release_id,
    )
    expected_view = _content_view(pinned_release_id, ProductID(course.oid))

    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = course
    enrollment_gw.with_product_and_student.return_value = enrollment
    release_reader.get_content.return_value = expected_view

    result = await handler.run(
        GetMyCourseContentQuery(actor_id=student, product_id=course.oid),
    )
    assert result is expected_view
    release_reader.get_content.assert_awaited_once_with(pinned_release_id)


async def test_missing_product_raises_404() -> None:
    handler, product_gw, _, _ = _make_handler()
    product_gw.with_id.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyCourseContentQuery(
                actor_id=_student(),
                product_id=ProductID(uuid.uuid4()),
            ),
        )


async def test_webinar_product_raises_404() -> None:
    webinar = Product.create_webinar(
        author_id=_author(),
        name=ProductTitle("Live SQL"),
    )
    handler, product_gw, _, _ = _make_handler()
    product_gw.with_id.return_value = webinar
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyCourseContentQuery(
                actor_id=_student(),
                product_id=webinar.oid,
            ),
        )


async def test_no_enrollment_raises_404() -> None:
    course = _course(_author())
    handler, product_gw, enrollment_gw, _ = _make_handler()
    product_gw.with_id.return_value = course
    enrollment_gw.with_product_and_student.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyCourseContentQuery(
                actor_id=_student(),
                product_id=course.oid,
            ),
        )


async def test_refunded_enrollment_raises_404() -> None:
    student = _student()
    course = _course(_author())
    refunded = _enrollment(
        ProductID(course.oid),
        student,
        status=EnrollmentStatus.REFUNDED,
    )
    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = course
    enrollment_gw.with_product_and_student.return_value = refunded
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyCourseContentQuery(actor_id=student, product_id=course.oid),
        )
    # Refunded → never even hits the reader.
    release_reader.get_content.assert_not_awaited()


async def test_completed_enrollment_still_sees_content() -> None:
    student = _student()
    course = _course(_author())
    pinned = CourseReleaseID(uuid.uuid4())
    completed = _enrollment(
        ProductID(course.oid),
        student,
        release_id=pinned,
        status=EnrollmentStatus.COMPLETED,
    )
    expected = _content_view(pinned, ProductID(course.oid))
    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = course
    enrollment_gw.with_product_and_student.return_value = completed
    release_reader.get_content.return_value = expected

    result = await handler.run(
        GetMyCourseContentQuery(actor_id=student, product_id=course.oid),
    )
    assert result is expected


async def test_missing_release_invariant_violation_404() -> None:
    student = _student()
    course = _course(_author())
    enrollment = _enrollment(ProductID(course.oid), student)
    handler, product_gw, enrollment_gw, release_reader = _make_handler()
    product_gw.with_id.return_value = course
    enrollment_gw.with_product_and_student.return_value = enrollment
    release_reader.get_content.return_value = None
    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GetMyCourseContentQuery(actor_id=student, product_id=course.oid),
        )
