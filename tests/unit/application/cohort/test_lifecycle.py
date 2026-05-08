from unittest.mock import AsyncMock

from learnic.application.commands.cohort.cancel import (
    CancelCohortCommand,
    CancelCohortCommandHandler,
)
from learnic.application.commands.cohort.close_enrollment import (
    CloseCohortEnrollmentCommand,
    CloseCohortEnrollmentCommandHandler,
)
from learnic.application.commands.cohort.complete import (
    CompleteCohortCommand,
    CompleteCohortCommandHandler,
)
from learnic.application.commands.cohort.mark_full import (
    MarkCohortFullCommand,
    MarkCohortFullCommandHandler,
)
from learnic.application.commands.cohort.open_enrollment import (
    OpenCohortEnrollmentCommand,
    OpenCohortEnrollmentCommandHandler,
)
from learnic.application.commands.cohort.start import (
    StartCohortCommand,
    StartCohortCommandHandler,
)
from learnic.entities.cohort.enums import (
    CohortEnrollmentStatus,
    CohortLifecycleStatus,
)
from learnic.entities.cohort.models import Cohort
from learnic.entities.user.models import UserID


async def test_close_then_open_enrollment(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort

    close = CloseCohortEnrollmentCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )
    await close.run(
        CloseCohortEnrollmentCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
        ),
    )
    assert cohort.enrollment_status is CohortEnrollmentStatus.CLOSED

    open_handler = OpenCohortEnrollmentCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )
    await open_handler.run(
        OpenCohortEnrollmentCommand(
            actor_id=host_id,
            cohort_id=cohort.oid,
        ),
    )
    assert cohort.enrollment_status is CohortEnrollmentStatus.OPEN


async def test_mark_full_sets_status(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    handler = MarkCohortFullCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )

    await handler.run(
        MarkCohortFullCommand(actor_id=host_id, cohort_id=cohort.oid),
    )
    assert cohort.enrollment_status is CohortEnrollmentStatus.FULL


async def test_lifecycle_start_complete_cancel(
    fake_transaction: AsyncMock,
    fake_cohort_gateway: AsyncMock,
    fake_product_gateway: AsyncMock,
    cohort: Cohort,
    host_id: UserID,
) -> None:
    fake_cohort_gateway.with_id.return_value = cohort
    start = StartCohortCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )
    await start.run(StartCohortCommand(actor_id=host_id, cohort_id=cohort.oid))
    assert cohort.lifecycle_status is CohortLifecycleStatus.ACTIVE

    complete = CompleteCohortCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )
    await complete.run(
        CompleteCohortCommand(actor_id=host_id, cohort_id=cohort.oid),
    )
    assert cohort.lifecycle_status is CohortLifecycleStatus.COMPLETED

    cancel = CancelCohortCommandHandler(
        transaction=fake_transaction,
        cohort_gateway=fake_cohort_gateway,
        product_gateway=fake_product_gateway,
    )
    await cancel.run(
        CancelCohortCommand(actor_id=host_id, cohort_id=cohort.oid),
    )
    assert cohort.lifecycle_status is CohortLifecycleStatus.CANCELLED
