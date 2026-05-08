import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.course_enrollment.complete import (
    CompleteCourseEnrollmentCommand,
    CompleteCourseEnrollmentCommandHandler,
)
from learnic.application.commands.course_enrollment.enroll import (
    EnrollStudentInCourseCommand,
    EnrollStudentInCourseCommandHandler,
)
from learnic.application.commands.course_enrollment.refund import (
    RefundCourseEnrollmentCommand,
    RefundCourseEnrollmentCommandHandler,
)
from learnic.application.commands.course_enrollment.update_progress import (
    UpdateCourseProgressCommand,
    UpdateCourseProgressCommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CannotEnrollInUnreleasedCourseError,
    NotACourseError,
    NotResourceOwnerError,
)
from learnic.entities.course_enrollment.enums import (
    CourseEnrollmentStatus,
)
from learnic.entities.course_enrollment.models import CourseEnrollment
from learnic.entities.course_release.enums import CourseReleaseKind
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.course_release.models import CourseRelease
from learnic.entities.course_release.value_objects import (
    CourseReleaseVersion,
)
from learnic.entities.product.models import Product
from learnic.entities.user.models import UserID


@pytest.fixture
def fake_course_enrollment_gateway() -> AsyncMock:
    g = AsyncMock()
    g.with_id = AsyncMock()
    g.with_product_and_student = AsyncMock(return_value=None)
    g.for_product = AsyncMock(return_value=[])
    return g


@pytest.fixture
def fake_release_gateway() -> AsyncMock:
    g = AsyncMock()
    g.with_id = AsyncMock()
    g.latest_for_product = AsyncMock()
    return g


@pytest.fixture
def student_id() -> UserID:
    return UserID(uuid.uuid4())


@pytest.fixture
def course_release(
    course_product: Product,
    author_id: UserID,
) -> CourseRelease:
    return CourseRelease(
        oid=CourseReleaseID(uuid.uuid4()),
        product_id=course_product.oid,
        ordinal=1,
        version=CourseReleaseVersion(1, 0, 0),
        kind=CourseReleaseKind.MAJOR,
        released_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc,
        ),
        released_by=author_id,
        notes=None,
    )


@pytest.fixture
def course_enrollment(
    course_product: Product,
    student_id: UserID,
    course_release: CourseRelease,
) -> CourseEnrollment:
    return CourseEnrollment.create(
        product_id=course_product.oid,
        student_id=student_id,
        release_id=course_release.oid,
    )


async def test_enroll_in_course_persists_and_returns_id(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    course_product: Product,
    course_release: CourseRelease,
    student_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_release_gateway.latest_for_product.return_value = course_release
    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_course_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    enrollment_id = await handler.run(
        EnrollStudentInCourseCommand(
            student_id=student_id,
            product_id=course_product.oid,
        ),
    )

    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, CourseEnrollment)
    assert saved.oid == enrollment_id
    assert saved.release_id == course_release.oid
    fake_transaction.commit.assert_awaited_once()


async def test_enroll_into_unreleased_course_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    course_product: Product,
    student_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_release_gateway.latest_for_product.return_value = None
    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_course_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    with pytest.raises(CannotEnrollInUnreleasedCourseError):
        await handler.run(
            EnrollStudentInCourseCommand(
                student_id=student_id,
                product_id=course_product.oid,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()


async def test_enroll_into_webinar_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    webinar_product: Product,
    student_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = webinar_product
    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_course_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    with pytest.raises(NotACourseError):
        await handler.run(
            EnrollStudentInCourseCommand(
                student_id=student_id,
                product_id=webinar_product.oid,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()


async def test_enroll_duplicate_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    course_product: Product,
    course_enrollment: CourseEnrollment,
    student_id: UserID,
) -> None:
    fake_product_gateway.with_id.return_value = course_product
    fake_course_enrollment_gateway.with_product_and_student.return_value = (
        course_enrollment
    )
    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_course_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    with pytest.raises(AlreadyEnrolledError):
        await handler.run(
            EnrollStudentInCourseCommand(
                student_id=student_id,
                product_id=course_product.oid,
            ),
        )


async def test_update_progress_by_student_succeeds(
    fake_transaction: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    course_enrollment: CourseEnrollment,
    student_id: UserID,
) -> None:
    fake_course_enrollment_gateway.with_id.return_value = course_enrollment
    handler = UpdateCourseProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_course_enrollment_gateway,
    )

    await handler.run(
        UpdateCourseProgressCommand(
            actor_id=student_id,
            enrollment_id=course_enrollment.oid,
            progress_percent=75,
        ),
    )
    assert course_enrollment.progress.value == 75
    assert course_enrollment.status is CourseEnrollmentStatus.ACTIVE


async def test_update_progress_to_100_auto_completes(
    fake_transaction: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    course_enrollment: CourseEnrollment,
    student_id: UserID,
) -> None:
    fake_course_enrollment_gateway.with_id.return_value = course_enrollment
    handler = UpdateCourseProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_course_enrollment_gateway,
    )

    await handler.run(
        UpdateCourseProgressCommand(
            actor_id=student_id,
            enrollment_id=course_enrollment.oid,
            progress_percent=100,
        ),
    )
    assert course_enrollment.progress.value == 100
    assert course_enrollment.status is CourseEnrollmentStatus.COMPLETED
    assert course_enrollment.completed_at is not None


async def test_update_progress_by_other_user_raises(
    fake_transaction: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    course_enrollment: CourseEnrollment,
    other_user_id: UserID,
) -> None:
    fake_course_enrollment_gateway.with_id.return_value = course_enrollment
    handler = UpdateCourseProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_course_enrollment_gateway,
    )

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            UpdateCourseProgressCommand(
                actor_id=other_user_id,
                enrollment_id=course_enrollment.oid,
                progress_percent=50,
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_complete_by_author_allowed(
    fake_transaction: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    course_enrollment: CourseEnrollment,
    course_product: Product,
    author_id: UserID,
) -> None:
    fake_course_enrollment_gateway.with_id.return_value = course_enrollment
    fake_product_gateway.with_id.return_value = course_product
    handler = CompleteCourseEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_course_enrollment_gateway,
        product_gateway=fake_product_gateway,
    )

    await handler.run(
        CompleteCourseEnrollmentCommand(
            actor_id=author_id,
            enrollment_id=course_enrollment.oid,
        ),
    )
    assert course_enrollment.status is CourseEnrollmentStatus.COMPLETED


async def test_refund_by_non_author_raises(
    fake_transaction: AsyncMock,
    fake_course_enrollment_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    course_enrollment: CourseEnrollment,
    course_product: Product,
    other_user_id: UserID,
) -> None:
    fake_course_enrollment_gateway.with_id.return_value = course_enrollment
    fake_product_gateway.with_id.return_value = course_product
    handler = RefundCourseEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_course_enrollment_gateway,
        product_gateway=fake_product_gateway,
    )

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            RefundCourseEnrollmentCommand(
                actor_id=other_user_id,
                enrollment_id=course_enrollment.oid,
            ),
        )
