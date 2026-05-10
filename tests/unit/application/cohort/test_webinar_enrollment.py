from unittest.mock import AsyncMock, MagicMock

import pytest

from learnic.application.commands.webinar_enrollment.complete import (
    CompleteWebinarEnrollmentCommand,
    CompleteWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_enrollment.drop import (
    DropWebinarEnrollmentCommand,
    DropWebinarEnrollmentCommandHandler,
)
from learnic.application.commands.webinar_enrollment.enroll import (
    EnrollStudentInCohortCommand,
    EnrollStudentInCohortCommandHandler,
)
from learnic.application.commands.webinar_enrollment.refund import (
    RefundWebinarEnrollmentCommand,
    RefundWebinarEnrollmentCommandHandler,
)
from learnic.application.common.errors import (
    AlreadyEnrolledError,
    CohortFullError,
    EnrollmentClosedError,
    EntityNotFoundError,
    InsufficientPermissionsError,
)
from learnic.entities.cohort.enums import CohortEnrollmentStatus
from learnic.entities.cohort.models import Cohort
from learnic.entities.product.value_objects import ParticipantsLimit
from learnic.entities.user.models import UserID
from learnic.entities.webinar_enrollment.enums import (
    WebinarEnrollmentStatus,
)
from learnic.entities.webinar_enrollment.models import WebinarEnrollment


@pytest.fixture
def fake_enrollment_gateway() -> AsyncMock:
    g = AsyncMock()
    g.with_id = AsyncMock()
    g.with_cohort_and_student = AsyncMock(return_value=None)
    g.for_cohort = AsyncMock(return_value=[])
    return g


@pytest.fixture
def existing_enrollment(cohort: Cohort) -> WebinarEnrollment:
    import uuid as _uuid  # noqa: PLC0415

    # A deliberately-unknown student so default tests treat the
    # actor as "someone else"; self-drop tests use the same
    # student_id as actor.
    return WebinarEnrollment.create(
        cohort_id=cohort.oid,
        student_id=UserID(_uuid.uuid4()),
    )


async def test_enroll_persists_and_returns_id(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    cohort: Cohort,
    stranger_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = EnrollStudentInCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )

    enrollment_id = await handler.run(
        EnrollStudentInCohortCommand(
            student_id=stranger_id,
            cohort_id=cohort.oid,
        ),
    )

    fake_entity_saver.add_one.assert_called_once()
    saved = fake_entity_saver.add_one.call_args.args[0]
    assert isinstance(saved, WebinarEnrollment)
    assert saved.oid == enrollment_id
    fake_transaction.commit.assert_awaited_once()


async def test_enroll_closed_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    cohort: Cohort,
    stranger_id: UserID,
) -> None:
    cohort.close_enrollment()
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
                student_id=stranger_id,
                cohort_id=cohort.oid,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()
    fake_transaction.commit.assert_not_called()


async def test_enroll_duplicate_raises(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    cohort: Cohort,
    existing_enrollment: WebinarEnrollment,
    stranger_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    fake_enrollment_gateway.with_cohort_and_student.return_value = existing_enrollment
    handler = EnrollStudentInCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )

    with pytest.raises(AlreadyEnrolledError):
        await handler.run(
            EnrollStudentInCohortCommand(
                student_id=stranger_id,
                cohort_id=cohort.oid,
            ),
        )
    fake_entity_saver.add_one.assert_not_called()


async def test_enroll_full_cohort_raises_and_marks_full(
    fake_transaction: AsyncMock,
    fake_entity_saver: MagicMock,
    fake_cohort_gateway: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    cohort: Cohort,
    existing_enrollment: WebinarEnrollment,
    stranger_id: UserID,
) -> None:
    cohort.change_max_participants(ParticipantsLimit(1))
    fake_cohort_gateway.with_id.return_value = cohort
    fake_enrollment_gateway.for_cohort.return_value = [existing_enrollment]
    handler = EnrollStudentInCohortCommandHandler(
        transaction=fake_transaction,
        entity_saver=fake_entity_saver,
        cohort_gateway=fake_cohort_gateway,
        enrollment_gateway=fake_enrollment_gateway,
    )

    with pytest.raises(CohortFullError):
        await handler.run(
            EnrollStudentInCohortCommand(
                student_id=stranger_id,
                cohort_id=cohort.oid,
            ),
        )
    assert cohort.enrollment_status is CohortEnrollmentStatus.FULL


async def test_drop_self_drop_allowed(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_enrollment: WebinarEnrollment,
) -> None:
    fake_enrollment_gateway.with_id.return_value = existing_enrollment
    handler = DropWebinarEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        DropWebinarEnrollmentCommand(
            actor_id=existing_enrollment.student_id,
            enrollment_id=existing_enrollment.oid,
        ),
    )

    assert existing_enrollment.status is WebinarEnrollmentStatus.DROPPED
    fake_cohort_gateway.with_id.assert_not_awaited()
    fake_transaction.commit.assert_awaited_once()


async def test_drop_by_host_allowed(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    cohort: Cohort,
    existing_enrollment: WebinarEnrollment,
    host_id: UserID,
) -> None:
    fake_enrollment_gateway.with_id.return_value = existing_enrollment
    fake_cohort_gateway.with_id.return_value = cohort
    handler = DropWebinarEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        DropWebinarEnrollmentCommand(
            actor_id=host_id,
            enrollment_id=existing_enrollment.oid,
        ),
    )
    assert existing_enrollment.status is WebinarEnrollmentStatus.DROPPED


async def test_drop_by_stranger_raises(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    cohort: Cohort,
    existing_enrollment: WebinarEnrollment,
    stranger_id: UserID,
) -> None:
    fake_enrollment_gateway.with_id.return_value = existing_enrollment
    fake_cohort_gateway.with_id.return_value = cohort
    fake_authorizer.require.side_effect = InsufficientPermissionsError(
        user_id=stranger_id,
        product_id=cohort.webinar_id,
        permission="MANAGE_RELEASES",
    )
    handler = DropWebinarEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    with pytest.raises(InsufficientPermissionsError):
        await handler.run(
            DropWebinarEnrollmentCommand(
                actor_id=stranger_id,
                enrollment_id=existing_enrollment.oid,
            ),
        )
    fake_transaction.commit.assert_not_called()


async def test_complete_by_host_allowed(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    cohort: Cohort,
    existing_enrollment: WebinarEnrollment,
    host_id: UserID,
) -> None:
    fake_enrollment_gateway.with_id.return_value = existing_enrollment
    fake_cohort_gateway.with_id.return_value = cohort
    handler = CompleteWebinarEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    await handler.run(
        CompleteWebinarEnrollmentCommand(
            actor_id=host_id,
            enrollment_id=existing_enrollment.oid,
        ),
    )
    assert existing_enrollment.status is WebinarEnrollmentStatus.COMPLETED


async def test_refund_missing_enrollment_raises(
    fake_transaction: AsyncMock,
    fake_enrollment_gateway: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_authorizer: AsyncMock,
    existing_enrollment: WebinarEnrollment,
    host_id: UserID,
) -> None:
    fake_enrollment_gateway.with_id.return_value = None
    handler = RefundWebinarEnrollmentCommandHandler(
        transaction=fake_transaction,
        enrollment_gateway=fake_enrollment_gateway,
        cohort_gateway=fake_cohort_gateway,
        authorizer=fake_authorizer,
    )

    with pytest.raises(EntityNotFoundError):
        await handler.run(
            RefundWebinarEnrollmentCommand(
                actor_id=host_id,
                enrollment_id=existing_enrollment.oid,
            ),
        )
