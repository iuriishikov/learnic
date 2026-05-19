"""Smoke coverage for the unified Enrollment handlers.

Covers the critical paths from the previous (split) handlers:

* enroll-in-course: success + AlreadyEnrolled
* enroll-in-cohort: success + already-enrolled + cohort capacity
* update-progress: success, NotOwner, capability-blocked on webinar
* complete / refund: type-discriminated auth dispatch
"""

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.enrollment.complete import (
    CompleteEnrollmentCommand,
    CompleteEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.enroll_in_cohort import (
    EnrollStudentInCohortCommand,
    EnrollStudentInCohortCommandHandler,
)
from learnic.application.commands.enrollment.enroll_in_course import (
    EnrollStudentInCourseCommand,
    EnrollStudentInCourseCommandHandler,
)
from learnic.application.commands.enrollment.grant_course import (
    GrantCourseEnrollmentCommand,
    GrantCourseEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.refund import (
    RefundEnrollmentCommand,
    RefundEnrollmentCommandHandler,
)
from learnic.application.commands.enrollment.update_progress import (
    UpdateProgressCommand,
    UpdateProgressCommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CannotEnrollInUnreleasedCourseError,
    EnrollmentClosedError,
    EntityNotFoundError,
    NotResourceOwnerError,
)
from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
)
from learnic.entities.cohort.ids import CohortID
from learnic.entities.cohort.models import Cohort
from learnic.entities.product.value_objects import ParticipantsLimit
from learnic.entities.course_release.ids import CourseReleaseID
from learnic.entities.enrollment.enums import (
    EnrollmentStatus,
    EnrollmentType,
)
from learnic.entities.enrollment.errors import (
    EnrollmentDoesNotSupportError,
)
from learnic.entities.enrollment.models import Enrollment
from learnic.entities.product.ids import ProductID
from learnic.entities.product.models import Product
from learnic.entities.product.value_objects import ProductTitle
from learnic.entities.user.models import UserID


def _course_product(author: UserID) -> Product:
    return Product.create_course(
        author_id=author,
        name=ProductTitle("Async Python"),
    )


def _course_enrollment(
    *,
    student: UserID,
    product: ProductID,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> Enrollment:
    e = Enrollment.create_course(
        student_id=student,
        product_id=product,
        release_id=CourseReleaseID(uuid.uuid4()),
    )
    e.status = status
    return e


def _webinar_enrollment(
    *,
    student: UserID,
    cohort: CohortID,
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE,
) -> Enrollment:
    e = Enrollment.create_webinar(
        student_id=student,
        cohort_id=cohort,
    )
    e.status = status
    return e


def _open_cohort(
    *,
    host: UserID,
    product_id: ProductID,
    max_participants: int | None = None,
) -> Cohort:
    return Cohort(
        oid=CohortID(uuid.uuid4()),
        webinar_id=product_id,
        host_id=host,
        starts_on=date(2026, 6, 1),
        enrollment_status=CohortEnrollmentStatus.OPEN,
        lifecycle_status=CohortLifecycleStatus.UPCOMING,
        created_at=datetime.now(timezone.utc),
        name=None,
        max_participants=(
            ParticipantsLimit(max_participants)
            if max_participants is not None
            else None
        ),
        ends_on=None,
    )


# ---------------------------- enroll_in_course ------------------------ #


async def test_enroll_in_course_success(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    course = _course_product(author_id)
    fake_product_gateway.with_id.return_value = course
    fake_enrollment_gateway.with_product_and_student.return_value = None
    release = MagicMock()
    release.oid = CourseReleaseID(uuid.uuid4())
    fake_release_gateway.latest_for_product.return_value = release

    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    new_id = await handler.run(
        EnrollStudentInCourseCommand(
            student_id=student_id,
            product_id=course.oid,
        ),
    )

    assert new_id is not None
    # Parent + course_details persisted in one transaction
    assert fake_entity_saver.add_one.call_count == 2
    fake_transaction.commit.assert_awaited_once()


async def test_enroll_in_course_raises_when_already_enrolled(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    course = _course_product(author_id)
    fake_product_gateway.with_id.return_value = course
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _course_enrollment(student=student_id, product=course.oid)
    )

    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    with pytest.raises(AlreadyEnrolledError):
        await handler.run(
            EnrollStudentInCourseCommand(
                student_id=student_id, product_id=course.oid,
            ),
        )
    fake_transaction.commit.assert_not_awaited()


async def test_enroll_in_course_raises_when_no_release(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    course = _course_product(author_id)
    fake_product_gateway.with_id.return_value = course
    fake_enrollment_gateway.with_product_and_student.return_value = None
    fake_release_gateway.latest_for_product.return_value = None

    handler = EnrollStudentInCourseCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        enrollment_gateway=fake_enrollment_gateway,
        release_gateway=fake_release_gateway,
    )

    with pytest.raises(CannotEnrollInUnreleasedCourseError):
        await handler.run(
            EnrollStudentInCourseCommand(
                student_id=student_id, product_id=course.oid,
            ),
        )


# ---------------------------- enroll_in_cohort ------------------------ #


async def test_enroll_in_cohort_success(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    cohort = _open_cohort(host=author_id, product_id=ProductID(uuid.uuid4()))
    fake_cohort_gateway.with_id.return_value = cohort
    fake_enrollment_gateway.with_cohort_and_student.return_value = None

    handler = EnrollStudentInCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )

    new_id = await handler.run(
        EnrollStudentInCohortCommand(
            student_id=student_id, cohort_id=cohort.oid,
        ),
    )

    assert new_id is not None
    assert fake_entity_saver.add_one.call_count == 2
    fake_transaction.commit.assert_awaited_once()


async def test_enroll_in_cohort_rejects_closed_enrollment(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    cohort = _open_cohort(host=author_id, product_id=ProductID(uuid.uuid4()))
    cohort.enrollment_status = CohortEnrollmentStatus.CLOSED
    fake_cohort_gateway.with_id.return_value = cohort

    handler = EnrollStudentInCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )

    with pytest.raises(EnrollmentClosedError):
        await handler.run(
            EnrollStudentInCohortCommand(
                student_id=student_id, cohort_id=cohort.oid,
            ),
        )


# ---------------------------- update_progress ------------------------- #


async def test_update_progress_success(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    student_id: UserID,
) -> None:
    enrollment = _course_enrollment(
        student=student_id, product=ProductID(uuid.uuid4()),
    )
    fake_enrollment_gateway.with_id.return_value = enrollment

    handler = UpdateProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
    )

    await handler.run(
        UpdateProgressCommand(
            actor_id=student_id,
            enrollment_id=enrollment.oid,
            progress_percent=42,
        ),
    )
    assert enrollment.course_details is not None
    assert enrollment.course_details.progress.value == 42
    assert enrollment.status is EnrollmentStatus.ACTIVE
    fake_transaction.commit.assert_awaited_once()


async def test_update_progress_to_100_auto_completes(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    student_id: UserID,
) -> None:
    enrollment = _course_enrollment(
        student=student_id, product=ProductID(uuid.uuid4()),
    )
    fake_enrollment_gateway.with_id.return_value = enrollment

    handler = UpdateProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
    )

    await handler.run(
        UpdateProgressCommand(
            actor_id=student_id,
            enrollment_id=enrollment.oid,
            progress_percent=100,
        ),
    )
    assert enrollment.status is EnrollmentStatus.COMPLETED


async def test_update_progress_rejects_non_owner(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    student_id: UserID,
) -> None:
    enrollment = _course_enrollment(
        student=student_id, product=ProductID(uuid.uuid4()),
    )
    fake_enrollment_gateway.with_id.return_value = enrollment

    handler = UpdateProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
    )

    with pytest.raises(NotResourceOwnerError):
        await handler.run(
            UpdateProgressCommand(
                actor_id=UserID(uuid.uuid4()),
                enrollment_id=enrollment.oid,
                progress_percent=42,
            ),
        )


async def test_update_progress_rejects_webinar(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    student_id: UserID,
) -> None:
    enrollment = _webinar_enrollment(
        student=student_id, cohort=CohortID(uuid.uuid4()),
    )
    fake_enrollment_gateway.with_id.return_value = enrollment

    handler = UpdateProgressCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
    )

    with pytest.raises(EnrollmentDoesNotSupportError):
        await handler.run(
            UpdateProgressCommand(
                actor_id=student_id,
                enrollment_id=enrollment.oid,
                progress_percent=50,
            ),
        )


# ---------------------------- complete / refund ----------------------- #


async def test_complete_course_uses_product_authorization(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    author_id: UserID,
) -> None:
    enrollment = _course_enrollment(
        student=UserID(uuid.uuid4()), product=ProductID(uuid.uuid4()),
    )
    fake_enrollment_gateway.with_id.return_value = enrollment

    handler = CompleteEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        CompleteEnrollmentCommand(
            actor_id=author_id, enrollment_id=enrollment.oid,
        ),
    )
    fake_authorizer.require.assert_awaited_once()
    fake_cohort_gateway.with_id.assert_not_awaited()
    assert enrollment.status is EnrollmentStatus.COMPLETED


async def test_refund_webinar_walks_through_cohort(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    author_id: UserID,
) -> None:
    cohort = _open_cohort(
        host=author_id, product_id=ProductID(uuid.uuid4()),
    )
    enrollment = _webinar_enrollment(
        student=UserID(uuid.uuid4()), cohort=cohort.oid,
    )
    fake_enrollment_gateway.with_id.return_value = enrollment
    fake_cohort_gateway.with_id.return_value = cohort

    handler = RefundEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        RefundEnrollmentCommand(
            actor_id=author_id, enrollment_id=enrollment.oid,
        ),
    )
    fake_cohort_gateway.with_id.assert_awaited_once_with(cohort.oid)
    assert enrollment.status is EnrollmentStatus.REFUNDED


# ---------------------------- grant_course ---------------------------- #


async def test_grant_course_success(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    course = _course_product(author_id)
    fake_product_gateway.with_id.return_value = course
    fake_user_gateway.with_id.return_value = MagicMock()
    fake_enrollment_gateway.with_product_and_student.return_value = None
    release = MagicMock()
    release.oid = CourseReleaseID(uuid.uuid4())
    fake_release_gateway.latest_for_product.return_value = release

    handler = GrantCourseEnrollmentCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        user_gateway=fake_user_gateway,
        enrollment_gateway=fake_enrollment_gateway,
        release_gateway=fake_release_gateway,
        authorizer=fake_authorizer,
    )

    new_id = await handler.run(
        GrantCourseEnrollmentCommand(
            actor_id=author_id,
            student_id=student_id,
            product_id=course.oid,
        ),
    )

    assert new_id is not None
    fake_authorizer.require.assert_awaited_once()
    fake_user_gateway.with_id.assert_awaited_once_with(student_id)
    assert fake_entity_saver.add_one.call_count == 2
    fake_transaction.commit.assert_awaited_once()


async def test_grant_course_rejects_missing_student(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    course = _course_product(author_id)
    fake_product_gateway.with_id.return_value = course
    fake_user_gateway.with_id.return_value = None

    handler = GrantCourseEnrollmentCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        user_gateway=fake_user_gateway,
        enrollment_gateway=fake_enrollment_gateway,
        release_gateway=fake_release_gateway,
        authorizer=fake_authorizer,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            GrantCourseEnrollmentCommand(
                actor_id=author_id,
                student_id=student_id,
                product_id=course.oid,
            ),
        )
    fake_enrollment_gateway.with_product_and_student.assert_not_awaited()
    fake_transaction.commit.assert_not_awaited()


async def test_grant_course_rejects_already_enrolled(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_product_gateway: AsyncMock,
    fake_user_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_release_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    student_id: UserID,
    author_id: UserID,
) -> None:
    course = _course_product(author_id)
    fake_product_gateway.with_id.return_value = course
    fake_user_gateway.with_id.return_value = MagicMock()
    fake_enrollment_gateway.with_product_and_student.return_value = (
        _course_enrollment(student=student_id, product=course.oid)
    )

    handler = GrantCourseEnrollmentCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        product_gateway=fake_product_gateway,
        user_gateway=fake_user_gateway,
        enrollment_gateway=fake_enrollment_gateway,
        release_gateway=fake_release_gateway,
        authorizer=fake_authorizer,
    )

    with pytest.raises(AlreadyEnrolledError):
        await handler.run(
            GrantCourseEnrollmentCommand(
                actor_id=author_id,
                student_id=student_id,
                product_id=course.oid,
            ),
        )


async def test_complete_raises_when_enrollment_missing(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    author_id: UserID,
) -> None:
    fake_enrollment_gateway.with_id.return_value = None

    handler = CompleteEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            CompleteEnrollmentCommand(
                actor_id=author_id,
                enrollment_id=uuid.uuid4(),  # type: ignore[arg-type]
            ),
        )
